# Admin routes for the Bowls Club application
from datetime import datetime, timedelta, date
from flask import render_template, flash, redirect, url_for, request, current_app, jsonify
from flask_login import login_required, current_user
from functools import wraps
import sqlalchemy as sa
import os
from markdown2 import markdown

from app.admin import bp
from app import db
from app.models import Member, Role, Event, Post, PolicyPage, Booking
from app.audit import audit_log_create, audit_log_update, audit_log_delete, audit_log_security_event, get_model_changes
from app.forms import EditMemberForm, PasswordResetForm, FlaskForm, WritePostForm
from app.utils import generate_secure_filename, get_secure_post_path, sanitize_html_content


def admin_required(f):
    """
    Decorator to restrict access to admin-only routes.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        if not current_user.is_admin:
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Non-admin user {current_user.username} attempted to access admin route')
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/manage_members')
@login_required
@admin_required
def manage_members():
    """
    Admin interface for managing members
    """
    try:
        # Get all members
        members = db.session.scalars(
            sa.select(Member).order_by(Member.lastname, Member.firstname)
        ).all()
        
        return render_template('admin/manage_members.html', members=members)
        
    except Exception as e:
        current_app.logger.error(f"Error in manage_members: {str(e)}")
        flash('An error occurred while loading members.', 'error')
        return redirect(url_for('main.index'))


@bp.route('/edit_member/<int:member_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_member(member_id):
    """
    Admin interface for editing or deleting a member
    """
    try:
        member = db.session.get(Member, member_id)
        if not member:
            flash('Member not found.', 'error')
            return redirect(url_for('admin.manage_members'))

        form = EditMemberForm(obj=member)
        form.member_id.data = member.id

        roles = db.session.scalars(sa.select(Role).order_by(Role.name)).all()
        form.roles.choices = [(role.id, role.name) for role in roles]

        # Pre-select member's roles for GET requests
        if request.method == 'GET':
            form.roles.data = [role.id for role in member.roles]

        # Normalize the submitted data for the roles field
        if request.method == 'POST':
            raw_roles = request.form.getlist('roles')
            form.roles.data = [int(role_id) for role_id in raw_roles]

        if form.validate_on_submit():
            if form.submit_update.data:
                # Prevent admin users from being locked out
                lockout_data = form.lockout.data
                if lockout_data and member.is_admin:
                    flash('Warning: Admin users cannot be locked out. Lockout setting ignored.', 'warning')
                    lockout_data = False
                
                # Capture changes for audit log
                changes = get_model_changes(member, {
                    'username': form.username.data,
                    'firstname': form.firstname.data,
                    'lastname': form.lastname.data,
                    'email': form.email.data,
                    'phone': form.phone.data,
                    'is_admin': form.is_admin.data,
                    'gender': form.gender.data,
                    'status': form.status.data,
                    'share_email': form.share_email.data,
                    'share_phone': form.share_phone.data,
                    'lockout': lockout_data
                })
                
                # Update member fields
                member.username = form.username.data
                member.firstname = form.firstname.data
                member.lastname = form.lastname.data
                member.email = form.email.data
                member.phone = form.phone.data
                member.is_admin = form.is_admin.data
                member.gender = form.gender.data
                member.status = form.status.data
                member.share_email = form.share_email.data
                member.share_phone = form.share_phone.data
                member.lockout = lockout_data

                selected_role_ids = form.roles.data
                selected_roles = db.session.scalars(sa.select(Role).where(Role.id.in_(selected_role_ids))).all()
                old_roles = [role.name for role in member.roles]
                new_roles = [role.name for role in selected_roles]
                if old_roles != new_roles:
                    changes['roles'] = old_roles
                member.roles = selected_roles

                db.session.commit()
                
                # Audit log the member update
                audit_log_update('Member', member.id, 
                               f'Updated member: {member.firstname} {member.lastname} ({member.username})',
                               changes)
                
                flash('Member updated successfully', 'success')
                return redirect(url_for('admin.manage_members'))
                
            elif form.submit_delete.data:
                # Capture member info for audit log before deletion
                member_info = f'{member.firstname} {member.lastname} ({member.username})'
                member_id = member.id
                
                # Delete the member
                db.session.delete(member)
                db.session.commit()
                
                # Audit log the member deletion
                audit_log_delete('Member', member_id, f'Deleted member: {member_info}')
                
                flash('Member deleted successfully', 'success')
                return redirect(url_for('admin.manage_members'))

        return render_template('edit_member.html', form=form, member=member)
        
    except Exception as e:
        current_app.logger.error(f"Error in edit_member: {str(e)}")
        flash('An error occurred while processing the member.', 'error')
        return redirect(url_for('admin.manage_members'))


@bp.route('/reset_member_password/<int:member_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_reset_password(member_id):
    """
    Admin interface for resetting a member's password
    """
    try:
        member = db.session.get(Member, member_id)
        if not member:
            flash('Member not found.', 'error')
            return redirect(url_for('admin.manage_members'))
        
        form = PasswordResetForm()
        
        if form.validate_on_submit():
            member.set_password(form.new_password.data)
            db.session.commit()
            
            # Audit log the password reset
            audit_log_update('Member', member.id, 
                           f'Password reset by admin for user: {member.username}', 
                           {'password': 'reset_by_admin'})
            
            flash(f'Password reset successfully for {member.firstname} {member.lastname}!', 'success')
            return redirect(url_for('admin.edit_member', member_id=member.id))
        
        return render_template('admin_reset_password.html', 
                             form=form, 
                             member=member,
                             form_title=f'Reset Password for {member.firstname} {member.lastname}',
                             form_action=url_for('admin.admin_reset_password', member_id=member.id))
        
    except Exception as e:
        current_app.logger.error(f"Error in admin_reset_password: {str(e)}")
        flash('An error occurred while processing the password reset.', 'error')
        return redirect(url_for('admin.edit_member', member_id=member_id))


@bp.route('/import_users')
@login_required
@admin_required
def import_users():
    """
    Admin interface for importing users from CSV
    """
    try:
        return render_template('admin/import_users.html')
        
    except Exception as e:
        current_app.logger.error(f"Error in import_users: {str(e)}")
        flash('An error occurred while loading the import page.', 'error')
        return redirect(url_for('main.index'))


@bp.route('/manage_roles', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_roles():
    """
    Admin interface for managing roles - create, rename, or delete roles
    """
    try:
        roles = db.session.scalars(sa.select(Role).order_by(Role.name)).all()
        
        # Get users with at least one role for the user roles section
        users_with_roles = db.session.scalars(
            sa.select(Member)
            .join(Member.roles)
            .order_by(Member.lastname, Member.firstname)
            .distinct()
        ).all()

        if request.method == 'POST':
            # Validate CSRF token
            csrf_form = FlaskForm()
            if not csrf_form.validate_on_submit():
                flash('Security validation failed.', 'error')
                return redirect(url_for('admin.manage_roles'))
                
            action = request.form.get('action')
            role_id = request.form.get('role_id')
            role_name = request.form.get('role_name', '').strip()
            user_id = request.form.get('user_id')

            if action == 'create' and role_name:
                # Create a new role
                if db.session.scalar(sa.select(Role).where(Role.name == role_name)):
                    flash('Role already exists.', 'error')
                else:
                    new_role = Role(name=role_name)
                    db.session.add(new_role)
                    db.session.commit()
                    
                    # Audit log the role creation
                    audit_log_create('Role', new_role.id, f'Created role: {role_name}')
                    
                    flash('Role created successfully.', 'success')

            elif action == 'rename' and role_id and role_name:
                # Rename an existing role
                role = db.session.get(Role, int(role_id))
                if role:
                    # Check if this is a core role
                    if role.name in current_app.config['CORE_ROLES']:
                        # Audit log the attempt to modify a core role
                        audit_log_security_event('CORE_ROLE_EDIT_ATTEMPT', 
                                               f'User attempted to rename core role "{role.name}"')
                        flash(f'Cannot rename core role "{role.name}". Core roles are protected.', 'error')
                    elif db.session.scalar(sa.select(Role).where(Role.name == role_name)):
                        flash('A role with this name already exists.', 'error')
                    else:
                        old_name = role.name
                        role.name = role_name
                        db.session.commit()
                        
                        # Audit log the role rename
                        audit_log_update('Role', role.id, f'Renamed role: {old_name} → {role_name}',
                                       {'name': old_name})
                        
                        flash('Role renamed successfully.', 'success')
                else:
                    flash('Role not found.', 'error')

            elif action == 'delete' and role_id:
                # Delete an existing role
                role = db.session.get(Role, int(role_id))
                if role:
                    # Check if this is a core role
                    if role.name in current_app.config['CORE_ROLES']:
                        # Audit log the attempt to delete a core role
                        audit_log_security_event('CORE_ROLE_DELETE_ATTEMPT', 
                                               f'User attempted to delete core role "{role.name}"')
                        flash(f'Cannot delete core role "{role.name}". Core roles are protected.', 'error')
                    else:
                        role_name = role.name
                        db.session.delete(role)
                        db.session.commit()
                        
                        # Audit log the role deletion
                        audit_log_delete('Role', role_id, f'Deleted role: {role_name}')
                        
                        flash('Role deleted successfully.', 'success')
                else:
                    flash('Role not found.', 'error')

            elif action == 'add_user_role' and user_id and role_id:
                # Add role to user
                user = db.session.get(Member, int(user_id))
                role = db.session.get(Role, int(role_id))
                
                if user and role:
                    if role not in user.roles:
                        user.roles.append(role)
                        db.session.commit()
                        
                        # Audit log the role assignment
                        audit_log_update('Member', user.id, 
                                       f'Added role "{role.name}" to user: {user.firstname} {user.lastname}',
                                       {'roles_added': [role.name]})
                        
                        flash(f'Role "{role.name}" added to {user.firstname} {user.lastname}.', 'success')
                    else:
                        flash(f'{user.firstname} {user.lastname} already has the role "{role.name}".', 'info')
                else:
                    flash('User or role not found.', 'error')

            elif action == 'remove_user_role' and user_id and role_id:
                # Remove role from user
                user = db.session.get(Member, int(user_id))
                role = db.session.get(Role, int(role_id))
                
                if user and role:
                    if role in user.roles:
                        user.roles.remove(role)
                        db.session.commit()
                        
                        # Audit log the role removal
                        audit_log_update('Member', user.id, 
                                       f'Removed role "{role.name}" from user: {user.firstname} {user.lastname}',
                                       {'roles_removed': [role.name]})
                        
                        flash(f'Role "{role.name}" removed from {user.firstname} {user.lastname}.', 'success')
                    else:
                        flash(f'{user.firstname} {user.lastname} does not have the role "{role.name}".', 'info')
                else:
                    flash('User or role not found.', 'error')

            return redirect(url_for('admin.manage_roles'))

        # Create a simple form for CSRF protection
        csrf_form = FlaskForm()
        
        return render_template('admin/manage_roles.html', 
                             roles=roles, 
                             users_with_roles=users_with_roles, 
                             csrf_form=csrf_form)
        
    except Exception as e:
        current_app.logger.error(f"Error in manage_roles: {str(e)}")
        flash('An error occurred while loading roles.', 'error')
        return redirect(url_for('main.index'))


@bp.route('/write_post', methods=['GET', 'POST'])
@login_required
@admin_required
def write_post():
    """
    Admin interface for writing posts
    """
    try:
        # Calculate default dates
        today = date.today()
        default_expires_on = today + timedelta(days=current_app.config.get('POST_EXPIRATION_DAYS', 30))
        
        if request.method == 'POST':
            # Validate CSRF token
            csrf_form = FlaskForm()
            if not csrf_form.validate_on_submit():
                flash('Security validation failed.', 'error')
                return redirect(url_for('admin.write_post'))
                
            # Process form submission
            title = request.form.get('title', '').strip()
            summary = request.form.get('summary', '').strip()
            content = request.form.get('content', '').strip()
            tags = request.form.get('tags', '').strip()
            
            # Parse dates
            try:
                publish_on = datetime.strptime(request.form.get('publish_on'), '%Y-%m-%d').date()
                expires_on = datetime.strptime(request.form.get('expires_on'), '%Y-%m-%d').date()
            except (ValueError, TypeError):
                flash('Invalid date format.', 'error')
                csrf_form = FlaskForm()
                return render_template('admin/write_post.html', 
                                     default_publish_on=today.isoformat(),
                                     default_expires_on=default_expires_on.isoformat(),
                                     csrf_form=csrf_form)
            
            # Validate required fields
            if not title or not summary or not content:
                flash('Title, summary, and content are required.', 'error')
                csrf_form = FlaskForm()
                return render_template('admin/write_post.html',
                                     default_publish_on=today.isoformat(),
                                     default_expires_on=default_expires_on.isoformat(),
                                     csrf_form=csrf_form)
            
            # Generate secure filenames using UUID
            markdown_filename = generate_secure_filename(title, '.md')
            html_filename = generate_secure_filename(title, '.html')
            
            # Create post in database
            post = Post(
                title=title,
                summary=summary,
                publish_on=publish_on,
                expires_on=expires_on,
                tags=tags,
                markdown_filename=markdown_filename,
                html_filename=html_filename,
                author_id=current_user.id
            )
            
            try:
                db.session.add(post)
                db.session.commit()
                
                # Create post directory if it doesn't exist
                post_dir = current_app.config['POSTS_STORAGE_PATH']
                os.makedirs(post_dir, exist_ok=True)
                
                # Get secure file paths
                markdown_path = get_secure_post_path(markdown_filename)
                html_path = get_secure_post_path(html_filename)
                
                # Validate secure paths
                if not markdown_path or not html_path:
                    db.session.rollback()
                    flash('Error creating secure file paths.', 'error')
                    csrf_form = FlaskForm()
                    return render_template('admin/write_post.html',
                                         default_publish_on=today.isoformat(),
                                         default_expires_on=default_expires_on.isoformat(),
                                         csrf_form=csrf_form)
                
                # Create markdown metadata header
                metadata = f"""---
title: {title}
summary: {summary}
publish_on: {publish_on.isoformat()}
expires_on: {expires_on.isoformat()}
tags: {tags}
---

"""
                
                # Save markdown file
                with open(markdown_path, 'w', encoding='utf-8') as markdown_file:
                    markdown_file.write(metadata + content)
                
                # Convert markdown to HTML and save
                html_content = markdown(content, extras=['fenced-code-blocks', 'tables'])
                sanitized_html = sanitize_html_content(html_content)
                
                with open(html_path, 'w', encoding='utf-8') as html_file:
                    html_file.write(sanitized_html)
                
                # Audit log the post creation
                audit_log_create('Post', post.id, f'Created post: {title}',
                               {'publish_on': publish_on.isoformat(), 'expires_on': expires_on.isoformat()})
                
                flash('Post created successfully!', 'success')
                return redirect(url_for('admin.manage_posts'))
                
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error creating post: {str(e)}")
                flash('An error occurred while creating the post.', 'error')
                csrf_form = FlaskForm()
                return render_template('admin/write_post.html',
                                     default_publish_on=today.isoformat(),
                                     default_expires_on=default_expires_on.isoformat(),
                                     csrf_form=csrf_form)
        
        # GET request - render form with default dates
        csrf_form = FlaskForm()
        return render_template('admin/write_post.html',
                             default_publish_on=today.isoformat(),
                             default_expires_on=default_expires_on.isoformat(),
                             csrf_form=csrf_form)
        
    except Exception as e:
        current_app.logger.error(f"Error in write_post: {str(e)}")
        flash('An error occurred while loading the write post page.', 'error')
        return redirect(url_for('main.index'))


@bp.route('/manage_posts')
@login_required
@admin_required
def manage_posts():
    """
    Admin interface for managing posts
    """
    try:
        # Get all posts
        posts = db.session.scalars(
            sa.select(Post).order_by(Post.publish_on.desc())
        ).all()
        
        # Create a simple form for CSRF protection
        csrf_form = FlaskForm()
        
        return render_template('admin/manage_posts.html', posts=posts, csrf_form=csrf_form)
        
    except Exception as e:
        current_app.logger.error(f"Error in manage_posts: {str(e)}")
        flash('An error occurred while loading posts.', 'error')
        return redirect(url_for('main.index'))


@bp.route('/manage_policy_pages')
@login_required
@admin_required
def manage_policy_pages():
    """
    Admin interface for managing policy pages
    """
    try:
        # Get all policy pages
        policy_pages = db.session.scalars(
            sa.select(PolicyPage).order_by(PolicyPage.sort_order, PolicyPage.title)
        ).all()
        
        return render_template('admin/manage_policy_pages.html', policy_pages=policy_pages)
        
    except Exception as e:
        current_app.logger.error(f"Error in manage_policy_pages: {str(e)}")
        flash('An error occurred while loading policy pages.', 'error')
        return redirect(url_for('main.index'))


@bp.route('/manage_events')
@login_required
@admin_required
def manage_events():
    """
    Admin interface for managing events
    """
    try:
        # Get all events
        events = db.session.scalars(
            sa.select(Event).order_by(Event.name)
        ).all()
        
        return render_template('admin/manage_events.html', events=events)
        
    except Exception as e:
        current_app.logger.error(f"Error in manage_events: {str(e)}")
        flash('An error occurred while loading events.', 'error')
        return redirect(url_for('main.index'))


# Placeholder templates return simple messages for now
@bp.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_post(post_id):
    """
    Admin interface for editing posts
    """
    try:
        from app.forms import WritePostForm
        from app.utils import get_secure_post_path, parse_metadata_from_markdown
        from markdown2 import markdown
        import yaml
        import os
        
        current_app.logger.info(f"Edit post request for post_id: {post_id}")
        
        post = db.session.get(Post, post_id)
        if not post:
            current_app.logger.error(f"Post not found with ID: {post_id}")
            flash('Post not found.', 'error')
            return redirect(url_for('admin.manage_posts'))

        current_app.logger.info(f"Found post: {post.title}, markdown: {post.markdown_filename}")

        # Load the post content from secure storage
        markdown_path = get_secure_post_path(post.markdown_filename)
        html_path = get_secure_post_path(post.html_filename)
        
        current_app.logger.info(f"Markdown path: {markdown_path}")
        current_app.logger.info(f"HTML path: {html_path}")
        
        if not markdown_path or not html_path:
            current_app.logger.error(f"Could not get secure paths for post files")
            flash('Post file paths could not be determined.', 'error')
            return redirect(url_for('admin.manage_posts'))
            
        if not os.path.exists(markdown_path):
            current_app.logger.error(f"Markdown file does not exist: {markdown_path}")
            flash('Post markdown file not found.', 'error')
            return redirect(url_for('admin.manage_posts'))

        with open(markdown_path, 'r') as file:
            markdown_content = file.read()

        # Parse metadata and content
        metadata, content = parse_metadata_from_markdown(markdown_content)

        # Prepopulate the form with post data
        form = WritePostForm(
            title=post.title,
            summary=post.summary,
            publish_on=post.publish_on,
            expires_on=post.expires_on,
            pin_until=post.pin_until,
            tags=post.tags,
            content=content
        )

        if form.validate_on_submit():
            # Capture changes for audit log
            changes = get_model_changes(post, {
                'title': form.title.data,
                'summary': form.summary.data,
                'publish_on': form.publish_on.data,
                'expires_on': form.expires_on.data,
                'pin_until': form.pin_until.data,
                'tags': form.tags.data
            })
            
            # Update the post metadata
            post.title = form.title.data
            post.summary = form.summary.data
            post.publish_on = form.publish_on.data
            post.expires_on = form.expires_on.data
            post.pin_until = form.pin_until.data
            post.tags = form.tags.data

            # Update the markdown file
            metadata_dict = {
                'title': form.title.data,
                'summary': form.summary.data,
                'publish_on': form.publish_on.data,
                'expires_on': form.expires_on.data,
                'pin_until': form.pin_until.data,
                'tags': form.tags.data,
                'author': post.author_id
            }
            metadata = "---\n" + yaml.dump(metadata_dict, default_flow_style=False) + "---\n"
            updated_markdown = metadata + "\n" + form.content.data

            with open(markdown_path, 'w') as file:
                file.write(updated_markdown)

            # Convert the updated Markdown to HTML and overwrite the HTML file
            updated_html = markdown(form.content.data, extras=["tables"])
            with open(html_path, 'w') as file:
                file.write(updated_html)

            # Save changes to the database
            db.session.commit()
            
            # Audit log the post update
            audit_log_update('Post', post.id, f'Updated post: {post.title}', changes)
            
            flash("Post updated successfully!", "success")
            return redirect(url_for('admin.manage_posts'))

        # Create CSRF form for template
        csrf_form = FlaskForm()
        return render_template('admin/write_post.html', form=form, post=post, csrf_form=csrf_form)
        
    except Exception as e:
        current_app.logger.error(f"Error in edit_post: {str(e)}")
        flash('An error occurred while editing the post.', 'error')
        return redirect(url_for('admin.manage_posts'))


@bp.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
@admin_required
def delete_post(post_id):
    """
    Admin interface for deleting posts
    """
    try:
        from app.utils import get_secure_post_path, get_secure_archive_path
        import os
        import shutil
        
        post = db.session.get(Post, post_id)
        if not post:
            flash('Post not found.', 'error')
            return redirect(url_for('admin.manage_posts'))

        # Capture post info for audit log before deletion
        post_info = f'{post.title} (ID: {post.id})'
        
        # Archive the post files before deletion
        markdown_path = get_secure_post_path(post.markdown_filename)
        html_path = get_secure_post_path(post.html_filename)
        
        if markdown_path and os.path.exists(markdown_path):
            archive_markdown_path = get_secure_archive_path(post.markdown_filename)
            if archive_markdown_path:
                shutil.move(markdown_path, archive_markdown_path)
                
        if html_path and os.path.exists(html_path):
            archive_html_path = get_secure_archive_path(post.html_filename)
            if archive_html_path:
                shutil.move(html_path, archive_html_path)

        # Delete the post from database
        db.session.delete(post)
        db.session.commit()
        
        # Audit log the post deletion
        audit_log_delete('Post', post_id, f'Deleted post: {post_info}')
        
        flash('Post deleted successfully.', 'success')
        return redirect(url_for('admin.manage_posts'))
        
    except Exception as e:
        current_app.logger.error(f"Error in delete_post: {str(e)}")
        flash('An error occurred while deleting the post.', 'error')
        return redirect(url_for('admin.manage_posts'))


@bp.route('/test')
@login_required
@admin_required
def test():
    return "Admin routes are working!"