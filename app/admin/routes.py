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
from app.models import Member, Role, Event, Post, PolicyPage, Booking, EventPool, PoolRegistration
from app.audit import audit_log_create, audit_log_update, audit_log_delete, audit_log_security_event, get_model_changes
from app.forms import EditMemberForm, ResetPasswordForm, FlaskForm, WritePostForm
from app.utils import generate_secure_filename, get_secure_post_path, sanitize_html_content
from app.routes import role_required

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
@role_required('User Manager')
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
@role_required('User Manager')
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

        return render_template('admin/edit_member.html', form=form, member=member)
        
    except Exception as e:
        current_app.logger.error(f"Error in edit_member: {str(e)}")
        flash('An error occurred while processing the member.', 'error')
        return redirect(url_for('admin.manage_members'))


@bp.route('/reset_member_password/<int:member_id>', methods=['GET', 'POST'])
@login_required
@role_required('User Manager')
def admin_reset_password(member_id):
    """
    Admin interface for resetting a member's password
    """
    try:
        member = db.session.get(Member, member_id)
        if not member:
            flash('Member not found.', 'error')
            return redirect(url_for('admin.manage_members'))
        
        form = ResetPasswordForm()
        
        if form.validate_on_submit():
            member.set_password(form.password.data)
            db.session.commit()
            
            # Audit log the password reset
            audit_log_update('Member', member.id, 
                           f'Password reset by admin for user: {member.username}', 
                           {'password': 'reset_by_admin'})
            
            flash(f'Password reset successfully for {member.firstname} {member.lastname}!', 'success')
            return redirect(url_for('admin.edit_member', member_id=member.id))
        
        return render_template('admin/admin_reset_password.html', 
                             form=form, 
                             member=member,
                             form_title=f'Reset Password for {member.firstname} {member.lastname}',
                             form_action=url_for('admin.admin_reset_password', member_id=member.id))
        
    except Exception as e:
        current_app.logger.error(f"Error in admin_reset_password: {str(e)}")
        flash('An error occurred while processing the password reset.', 'error')
        return redirect(url_for('admin.edit_member', member_id=member_id))


@bp.route('/import_users', methods=['GET', 'POST'])
@login_required
@admin_required
def import_users():
    """
    Admin interface for importing users from CSV
    - Required columns: firstname, lastname, email, phone
    - Optional columns: username, gender
    - Imported users get 'pending' status and no roles
    """
    try:
        from app.forms import ImportUsersForm
        from app.audit import audit_log_bulk_operation
        import csv
        import io
        
        form = ImportUsersForm()
        results = None
        
        if form.validate_on_submit():
            csv_file = form.csv_file.data
            
            # Read CSV content
            try:
                # Decode the file content
                csv_content = csv_file.read().decode('utf-8')
                csv_file.seek(0)  # Reset file pointer
                
                # Parse CSV
                csv_reader = csv.DictReader(io.StringIO(csv_content))
                
                # Validate required columns
                required_columns = {'firstname', 'lastname', 'email', 'phone'}
                csv_columns = set(csv_reader.fieldnames or [])
                
                if not required_columns.issubset(csv_columns):
                    missing_columns = required_columns - csv_columns
                    flash(f'CSV file is missing required columns: {", ".join(missing_columns)}', 'error')
                    return render_template('admin/import_users.html', form=form, results=results)
                
                # Process rows
                success_count = 0
                error_count = 0
                errors = []
                
                for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 to account for header
                    try:
                        # Extract required fields
                        firstname = row['firstname'].strip()
                        lastname = row['lastname'].strip()
                        email = row['email'].strip().lower()
                        phone = row['phone'].strip()
                        
                        # Validate required fields
                        if not all([firstname, lastname, email, phone]):
                            errors.append(f'Row {row_num}: Missing required data')
                            error_count += 1
                            continue
                        
                        # Check if email already exists
                        existing_user = db.session.scalar(sa.select(Member).where(Member.email == email))
                        if existing_user:
                            errors.append(f'Row {row_num}: Email {email} already exists')
                            error_count += 1
                            continue
                        
                        # Generate username if not provided
                        username = row.get('username', '').strip()
                        if not username:
                            username = f"{firstname.lower()}_{lastname.lower()}"
                            # Make username unique if it already exists
                            base_username = username
                            counter = 1
                            while db.session.scalar(sa.select(Member).where(Member.username == username)):
                                username = f"{base_username}_{counter}"
                                counter += 1
                        else:
                            # Check if provided username already exists
                            existing_username = db.session.scalar(sa.select(Member).where(Member.username == username))
                            if existing_username:
                                errors.append(f'Row {row_num}: Username {username} already exists')
                                error_count += 1
                                continue
                        
                        # Get gender, default to 'unknown' if not provided
                        gender = row.get('gender', '').strip()
                        if gender.lower() not in ['male', 'female', 'other']:
                            gender = 'Other'
                        else:
                            gender = gender.capitalize()
                        
                        # Create new member
                        member = Member(
                            username=username,
                            firstname=firstname,
                            lastname=lastname,
                            email=email,
                            phone=phone,
                            gender=gender,
                            status='Pending',  # All imported users get pending status
                            is_admin=False,    # No admin privileges
                            share_email=True,  # Default privacy settings
                            share_phone=True
                        )
                        
                        db.session.add(member)
                        success_count += 1
                        
                    except Exception as e:
                        errors.append(f'Row {row_num}: {str(e)}')
                        error_count += 1
                        continue
                
                # Commit all successful imports
                if success_count > 0:
                    db.session.commit()
                    
                    # Audit log the bulk import
                    audit_log_bulk_operation('BULK_CREATE', 'Member', success_count, 
                                           f'CSV import: {success_count} members imported, {error_count} errors')
                    
                    flash(f'Successfully imported {success_count} users.', 'success')
                
                if error_count > 0:
                    flash(f'{error_count} errors occurred during import.', 'warning')
                
                results = {
                    'success_count': success_count,
                    'error_count': error_count,
                    'errors': errors
                }
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error processing CSV file: {str(e)}', 'error')
        
        return render_template('admin/import_users.html', form=form, results=results)
        
    except Exception as e:
        current_app.logger.error(f"Error in import_users: {str(e)}")
        flash('An error occurred while loading the import page.', 'error')
        return redirect(url_for('main.index'))


@bp.route('/manage_roles', methods=['GET', 'POST'])
@login_required
@role_required('User Manager')
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
                             csrf_form=csrf_form,
                             core_roles=current_app.config.get('CORE_ROLES', []))
        
    except Exception as e:
        current_app.logger.error(f"Error in manage_roles: {str(e)}")
        flash('An error occurred while loading roles.', 'error')
        return redirect(url_for('main.index'))


@bp.route('/write_post', methods=['GET', 'POST'])
@login_required
@role_required('Content Manager')
def write_post():
    """
    Admin interface for writing posts
    """
    try:
        from app.forms import WritePostForm
        
        # Create form instance
        form = WritePostForm()
        
        if form.validate_on_submit():
            # Get form data
            title = form.title.data.strip()
            summary = form.summary.data.strip()
            content = request.form.get('content', '').strip()  # Content field might not be in the form
            tags = form.tags.data.strip() if form.tags.data else ''
            publish_on = form.publish_on.data
            expires_on = form.expires_on.data
            pin_until = form.pin_until.data
            
            # Validate required fields
            if not title or not summary or not content:
                flash('Title, summary, and content are required.', 'error')
                return render_template('admin/write_post.html', form=form)
            
            # Generate secure filenames using UUID
            markdown_filename = generate_secure_filename(title, '.md')
            html_filename = generate_secure_filename(title, '.html')
            
            # Create post in database
            post = Post(
                title=title,
                summary=summary,
                publish_on=publish_on,
                expires_on=expires_on,
                pin_until=pin_until,
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
                    return render_template('admin/write_post.html', form=form)
                
                # Create markdown metadata header
                metadata = f"""---
title: {title}
summary: {summary}
publish_on: {publish_on.isoformat()}
expires_on: {expires_on.isoformat()}
pin_until: {pin_until.isoformat() if pin_until else ''}
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
                return render_template('admin/write_post.html', form=form)
        
        # GET request - render form
        return render_template('admin/write_post.html', form=form)
        
    except Exception as e:
        current_app.logger.error(f"Error in write_post: {str(e)}")
        flash('An error occurred while loading the write post page.', 'error')
        return redirect(url_for('main.index'))


@bp.route('/manage_posts', methods=['GET', 'POST'])
@login_required
@role_required('Content Manager')
def manage_posts():
    """
    Admin interface for managing posts with bulk operations
    """
    try:
        from app.utils import get_secure_post_path, get_secure_archive_path
        import shutil
        
        today = date.today()
        posts_query = sa.select(Post).order_by(Post.created_at.desc())
        posts = db.session.scalars(posts_query).all()

        if request.method == 'POST':
            # Validate CSRF token
            csrf_form = FlaskForm()
            if not csrf_form.validate_on_submit():
                flash('Security validation failed.', 'error')
                return redirect(url_for('admin.manage_posts'))
                
            # Handle deletion of selected posts
            post_ids = request.form.getlist('post_ids')
            deleted_posts = []
            
            for post_id in post_ids:
                post = db.session.get(Post, post_id)
                if post:
                    # Capture post info for audit log
                    deleted_posts.append(f'{post.title} (ID: {post.id})')
                    
                    # Move files to secure archive storage
                    markdown_path = get_secure_post_path(post.markdown_filename)
                    html_path = get_secure_post_path(post.html_filename)
                    archive_markdown_path = get_secure_archive_path(post.markdown_filename)
                    archive_html_path = get_secure_archive_path(post.html_filename)
                    
                    # Validate all paths
                    if not all([markdown_path, html_path, archive_markdown_path, archive_html_path]):
                        continue  # Skip files with invalid paths

                    # Ensure the archive directory exists
                    archive_dir = current_app.config['ARCHIVE_STORAGE_PATH']
                    os.makedirs(archive_dir, exist_ok=True)

                    # Move Markdown file if it exists
                    if os.path.exists(markdown_path):
                        shutil.move(markdown_path, archive_markdown_path)

                    # Move HTML file if it exists
                    if os.path.exists(html_path):
                        shutil.move(html_path, archive_html_path)

                    # Delete post from database
                    db.session.delete(post)
            
            db.session.commit()
            
            # Audit log the post deletions
            if deleted_posts:
                from app.audit import audit_log_bulk_operation
                audit_log_bulk_operation('BULK_DELETE', 'Post', len(deleted_posts), 
                                       f'Deleted {len(deleted_posts)} posts: {", ".join(deleted_posts)}')
            flash(f"{len(post_ids)} post(s) deleted successfully!", "success")
            return redirect(url_for('admin.manage_posts'))

        # Create a simple form for CSRF protection
        csrf_form = FlaskForm()
        
        return render_template('admin/manage_posts.html', 
                             posts=posts, 
                             today=today,
                             csrf_form=csrf_form)
        
    except Exception as e:
        current_app.logger.error(f"Error in manage_posts: {str(e)}")
        flash('An error occurred while loading posts.', 'error')
        return redirect(url_for('main.index'))


@bp.route('/manage_policy_pages')
@login_required
@role_required('Content Manager')
def manage_policy_pages():
    """
    Admin interface for managing policy pages
    """
    try:
        # Get all policy pages
        policy_pages = db.session.scalars(
            sa.select(PolicyPage).order_by(PolicyPage.sort_order, PolicyPage.title)
        ).all()
        
        # Check if we should show orphaned files
        show_orphaned = request.args.get('show_orphaned', '').lower() == 'true'
        orphaned_pages = []
        
        if show_orphaned:
            from app.utils import find_orphaned_policy_pages
            orphaned_pages = find_orphaned_policy_pages()
            
            # Provide feedback message if no orphaned files found
            if not orphaned_pages:
                flash('No orphaned policy page files found! All files are properly tracked in the database.', 'success')
        
        # Create a simple form for CSRF protection
        csrf_form = FlaskForm()
        
        return render_template('admin/manage_policy_pages.html', 
                             policy_pages=policy_pages, 
                             csrf_form=csrf_form,
                             show_orphaned=show_orphaned,
                             orphaned_pages=orphaned_pages)
        
    except Exception as e:
        current_app.logger.error(f"Error in manage_policy_pages: {str(e)}")
        flash('An error occurred while loading policy pages.', 'error')
        return redirect(url_for('main.index'))


@bp.route('/manage_events', methods=['GET', 'POST'])
@login_required
@role_required('Event Manager')
def manage_events():
    """
    Admin interface for managing events
    """
    try:
        from app.forms import EventForm, EventSelectionForm, BookingForm
        from app.models import EventTeam, Booking
        from app.audit import audit_log_create, audit_log_update
        
        # Get selected event ID from request
        selected_event_id = request.args.get('event_id', type=int) or request.form.get('event_id', type=int)
        selected_event = None
        event_teams = []
        event_bookings = []
        can_create_bookings = False
        
        # Initialize forms
        selection_form = EventSelectionForm()
        event_form = EventForm()
        booking_form = BookingForm()
        
        # Handle form submissions
        if request.method == 'POST':
            # Handle event creation/updating
            if 'submit' in request.form and event_form.validate_on_submit():
                if event_form.event_id.data:
                    # Update existing event
                    event = db.session.get(Event, event_form.event_id.data)
                    if event:
                        # Capture changes for audit log
                        changes = get_model_changes(event, {
                            'name': event_form.name.data,
                            'event_type': event_form.event_type.data,
                            'gender': event_form.gender.data,
                            'format': event_form.format.data,
                            'scoring': event_form.scoring.data
                        })
                        
                        # Update event
                        event.name = event_form.name.data
                        event.event_type = event_form.event_type.data
                        event.gender = event_form.gender.data
                        event.format = event_form.format.data
                        event.scoring = event_form.scoring.data
                        
                        # Update event managers
                        event.event_managers.clear()
                        for manager_id in event_form.event_managers.data:
                            manager = db.session.get(Member, manager_id)
                            if manager:
                                event.event_managers.append(manager)
                        
                        db.session.commit()
                        
                        # Audit log
                        audit_log_update('Event', event.id, f'Updated event: {event.name}', changes)
                        
                        flash(f'Event "{event.name}" updated successfully!', 'success')
                        selected_event_id = event.id
                else:
                    # Create new event
                    event = Event(
                        name=event_form.name.data,
                        event_type=event_form.event_type.data,
                        gender=event_form.gender.data,
                        format=event_form.format.data,
                        scoring=event_form.scoring.data
                    )
                    
                    # Add event managers
                    for manager_id in event_form.event_managers.data:
                        manager = db.session.get(Member, manager_id)
                        if manager:
                            event.event_managers.append(manager)
                    
                    db.session.add(event)
                    db.session.flush()  # Get event ID
                    
                    # Automatically create a pool for the new event (open by default)
                    event_pool = EventPool(
                        event_id=event.id,
                        is_open=True
                    )
                    event.has_pool = True
                    db.session.add(event_pool)
                    
                    db.session.commit()
                    
                    # Audit log
                    audit_log_create('Event', event.id, f'Created event: {event.name}')
                    audit_log_create('EventPool', event_pool.id, f'Auto-created pool for event: {event.name}')
                    
                    flash(f'Event "{event.name}" created successfully with pool registration open!', 'success')
                    selected_event_id = event.id
            
            # Handle booking creation/updating
            elif 'create_booking' in request.form and booking_form.validate_on_submit():
                if selected_event_id:
                    # Create new booking
                    booking = Booking(
                        booking_date=booking_form.booking_date.data,
                        session=booking_form.session.data,
                        organizer_id=current_user.id,
                        rink_count=booking_form.rink_count.data,
                        booking_type='event',
                        priority=booking_form.priority.data,
                        vs=booking_form.vs.data,
                        home_away=booking_form.home_away.data,
                        event_id=selected_event_id
                    )
                    
                    db.session.add(booking)
                    db.session.commit()
                    
                    # Audit log
                    audit_log_create('Booking', booking.id, f'Created event booking for {booking.booking_date}')
                    
                    flash('Booking created successfully!', 'success')
        
        # Get selected event and related data
        if selected_event_id:
            selected_event = db.session.get(Event, selected_event_id)
            if selected_event:
                # Get event teams
                event_teams = db.session.scalars(
                    sa.select(EventTeam).where(EventTeam.event_id == selected_event_id)
                    .order_by(EventTeam.team_name)
                ).all()
                
                # Get event bookings
                event_bookings = db.session.scalars(
                    sa.select(Booking).where(Booking.event_id == selected_event_id)
                    .order_by(Booking.booking_date, Booking.session)
                ).all()
                
                # Check if we can create bookings (need at least one team)
                can_create_bookings = len(event_teams) > 0
                
                # Pre-populate event form with selected event data
                if request.method == 'GET':
                    event_form.event_id.data = selected_event.id
                    event_form.name.data = selected_event.name
                    event_form.event_type.data = selected_event.event_type
                    event_form.gender.data = selected_event.gender
                    event_form.format.data = selected_event.format
                    event_form.scoring.data = selected_event.scoring
                    event_form.event_managers.data = [manager.id for manager in selected_event.event_managers]
                
                # Set selection form to selected event
                selection_form.selected_event.data = selected_event_id
        
        # Get pool data if event has pool enabled
        pool_data = None
        pool_registrations = []
        if selected_event and selected_event.has_pool_enabled():
            pool_registrations = db.session.scalars(
                sa.select(PoolRegistration)
                .join(PoolRegistration.member)
                .where(PoolRegistration.pool_id == selected_event.pool.id)
                .order_by(Member.firstname, Member.lastname)
            ).all()
            
            pool_data = {
                'pool': selected_event.pool,
                'total_registrations': len(pool_registrations),
                'registered_count': len([r for r in pool_registrations if r.status == 'registered']),
                'available_count': len([r for r in pool_registrations if r.status == 'available']),
                'selected_count': len([r for r in pool_registrations if r.status == 'selected']),
                'withdrawn_count': len([r for r in pool_registrations if r.status == 'withdrawn'])
            }
        
        # Get team positions for display
        team_positions = current_app.config.get('TEAM_POSITIONS', {})
        
        # Get available members for adding to pool (members not already in the pool)
        available_members_for_pool = []
        if selected_event and selected_event.has_pool_enabled():
            # Get all active members
            all_members = db.session.scalars(
                sa.select(Member)
                .where(Member.status.in_(['Full', 'Social', 'Life']))
                .order_by(Member.firstname, Member.lastname)
            ).all()
            
            # Filter out members already in the pool
            pool_member_ids = set()
            if pool_registrations:
                pool_member_ids = {reg.member_id for reg in pool_registrations if reg.is_active}
            
            available_members_for_pool = [member for member in all_members if member.id not in pool_member_ids]
        
        return render_template('admin/manage_events.html', 
                             events=[], # Not used in template
                             selection_form=selection_form,
                             event_form=event_form,
                             booking_form=booking_form,
                             selected_event=selected_event,
                             event_teams=event_teams,
                             event_bookings=event_bookings,
                             can_create_bookings=can_create_bookings,
                             team_positions=team_positions,
                             pool_data=pool_data,
                             pool_registrations=pool_registrations,
                             available_members_for_pool=available_members_for_pool)
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f"Error in manage_events: {str(e)}")
        current_app.logger.error(f"Full traceback: {error_details}")
        current_app.logger.error(f"Request args: {request.args}")
        current_app.logger.error(f"Request form: {request.form}")
        flash(f'An error occurred while loading events: {str(e)}', 'error')
        return redirect(url_for('main.index'))


@bp.route('/toggle_event_pool/<int:event_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def toggle_event_pool(event_id):
    """
    Toggle pool registration status for an event (open/close)
    """
    try:
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        event = db.session.get(Event, event_id)
        if not event:
            flash('Event not found.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Check if event has pool enabled
        if not event.has_pool_enabled():
            flash('This event does not have pool registration enabled.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Toggle pool status
        if event.pool.is_open:
            event.pool.close_pool()
            flash(f'Pool registration for "{event.name}" has been closed.', 'info')
            action = 'closed'
        else:
            event.pool.reopen_pool()
            flash(f'Pool registration for "{event.name}" has been reopened.', 'success')
            action = 'reopened'
        
        db.session.commit()
        
        # Audit log
        audit_log_update('EventPool', event.pool.id, 
                        f'Pool registration {action} for event: {event.name}')
        
        return redirect(url_for('admin.manage_events', event_id=event_id))
        
    except Exception as e:
        current_app.logger.error(f"Error toggling event pool: {str(e)}")
        flash('An error occurred while updating pool status.', 'error')
        return redirect(url_for('admin.manage_events'))


@bp.route('/create_event_pool/<int:event_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def create_event_pool(event_id):
    """
    Create a new pool for an event
    """
    try:
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        event = db.session.get(Event, event_id)
        if not event:
            flash('Event not found.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Check if event already has a pool
        if event.has_pool_enabled():
            flash('This event already has pool registration enabled.', 'warning')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Create new pool
        new_pool = EventPool(
            event_id=event_id,
            is_open=True
        )
        
        # Enable pool on event
        event.has_pool = True
        
        db.session.add(new_pool)
        db.session.commit()
        
        # Audit log
        audit_log_create('EventPool', new_pool.id, 
                        f'Created pool for event: {event.name}')
        
        flash(f'Pool registration has been enabled for "{event.name}".', 'success')
        return redirect(url_for('admin.manage_events', event_id=event_id))
        
    except Exception as e:
        current_app.logger.error(f"Error creating event pool: {str(e)}")
        flash('An error occurred while creating the pool.', 'error')
        return redirect(url_for('admin.manage_events'))


@bp.route('/update_registration_status/<int:registration_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def update_registration_status(registration_id):
    """
    Update a pool registration status (for Event Managers)
    """
    try:
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        new_status = request.form.get('status')
        if new_status not in PoolRegistration.get_valid_statuses():
            flash('Invalid status.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        registration = db.session.get(PoolRegistration, registration_id)
        if not registration:
            flash('Registration not found.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        old_status = registration.status
        event_id = registration.pool.event_id
        member_name = f"{registration.member.firstname} {registration.member.lastname}"
        
        # Update status
        if new_status == 'registered':
            registration.reregister()
        elif new_status == 'available':
            registration.set_available()
        elif new_status == 'selected':
            registration.set_selected()
        elif new_status == 'withdrawn':
            registration.withdraw()
        
        db.session.commit()
        
        # Audit log
        audit_log_update('PoolRegistration', registration.id, 
                        f'Status updated from {old_status} to {new_status} for {member_name}')
        
        flash(f'{member_name} status updated to {new_status.title()}.', 'success')
        return redirect(url_for('admin.manage_events', event_id=event_id))
        
    except Exception as e:
        current_app.logger.error(f"Error updating registration status: {str(e)}")
        flash('An error occurred while updating the registration status.', 'error')
        return redirect(url_for('admin.manage_events'))


# Placeholder templates return simple messages for now
@bp.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
@login_required
@role_required('Content Manager')
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
@role_required('Content Manager')
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


@bp.route('/create_policy_page', methods=['GET', 'POST'])
@login_required
@role_required('Content Manager')
def create_policy_page():
    """
    Admin interface for creating policy pages
    """
    try:
        from app.forms import PolicyPageForm
        from app.utils import generate_secure_filename, get_secure_policy_page_path
        import yaml
        import os
        from markdown2 import markdown
        
        form = PolicyPageForm()
        
        if form.validate_on_submit():
            # Check if slug already exists
            existing_page = db.session.scalar(
                sa.select(PolicyPage).where(PolicyPage.slug == form.slug.data)
            )
            if existing_page:
                flash('A policy page with this URL slug already exists. Please choose a different slug.', 'error')
                return render_template('admin/policy_page_form.html', form=form, title="Create Policy Page")
            
            # Generate secure filenames using UUID
            markdown_filename = generate_secure_filename(form.title.data, '.md')
            html_filename = generate_secure_filename(form.title.data, '.html')
            
            # Save metadata to the database
            policy_page = PolicyPage(
                title=form.title.data,
                slug=form.slug.data,
                description=form.description.data,
                is_active=form.is_active.data,
                show_in_footer=form.show_in_footer.data,
                sort_order=form.sort_order.data or 0,
                author_id=current_user.id,
                markdown_filename=markdown_filename,
                html_filename=html_filename
            )
            db.session.add(policy_page)
            db.session.commit()
            
            # Audit log the policy page creation
            audit_log_create('PolicyPage', policy_page.id, f'Created policy page: {policy_page.title}',
                            {'slug': policy_page.slug, 'is_active': policy_page.is_active})
            
            # Save content to secure storage
            policy_dir = current_app.config['POLICY_PAGES_STORAGE_PATH']
            os.makedirs(policy_dir, exist_ok=True)
            markdown_path = get_secure_policy_page_path(markdown_filename)
            html_path = get_secure_policy_page_path(html_filename)
            
            # Validate secure paths
            if not markdown_path or not html_path:
                flash('Error creating secure file paths.', 'error')
                return render_template('admin/policy_page_form.html', form=form, title="Create Policy Page")
            
            # Create metadata dictionary and serialize to YAML
            metadata_dict = {
                'title': policy_page.title,
                'slug': policy_page.slug,
                'description': policy_page.description,
                'is_active': policy_page.is_active,
                'show_in_footer': policy_page.show_in_footer,
                'sort_order': policy_page.sort_order,
                'author': policy_page.author_id
            }
            metadata = "---\n" + yaml.dump(metadata_dict, default_flow_style=False) + "---\n"
            
            # Write markdown file with metadata
            with open(markdown_path, 'w', encoding='utf-8') as f:
                f.write(metadata + "\n" + form.content.data)
            
            # Convert to HTML and write HTML file
            html_content = markdown(form.content.data, extras=['fenced-code-blocks', 'tables'])
            sanitized_html = sanitize_html_content(html_content)
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(sanitized_html)
            
            flash('Policy page created successfully!', 'success')
            return redirect(url_for('admin.manage_policy_pages'))
        
        return render_template('admin/policy_page_form.html', form=form, title="Create Policy Page")
        
    except Exception as e:
        current_app.logger.error(f"Error in create_policy_page: {str(e)}")
        flash('An error occurred while creating the policy page.', 'error')
        return redirect(url_for('admin.manage_policy_pages'))


@bp.route('/edit_policy_page/<int:policy_page_id>', methods=['GET', 'POST'])
@login_required
@role_required('Content Manager')
def edit_policy_page(policy_page_id):
    """
    Admin interface for editing policy pages
    """
    try:
        from app.forms import PolicyPageForm
        from app.utils import get_secure_policy_page_path, parse_metadata_from_markdown
        import yaml
        import os
        from markdown2 import markdown
        
        policy_page = db.session.get(PolicyPage, policy_page_id)
        if not policy_page:
            flash('Policy page not found.', 'error')
            return redirect(url_for('admin.manage_policy_pages'))
        
        form = PolicyPageForm(obj=policy_page)
        
        if form.validate_on_submit():
            # Check if slug already exists (but not for this page)
            existing_page = db.session.scalar(
                sa.select(PolicyPage).where(PolicyPage.slug == form.slug.data, PolicyPage.id != policy_page_id)
            )
            if existing_page:
                flash('A policy page with this URL slug already exists. Please choose a different slug.', 'error')
                return render_template('admin/policy_page_form.html', form=form, title="Edit Policy Page")
            
            # Capture changes for audit log
            changes = get_model_changes(policy_page, {
                'title': form.title.data,
                'slug': form.slug.data,
                'description': form.description.data,
                'is_active': form.is_active.data,
                'show_in_footer': form.show_in_footer.data,
                'sort_order': form.sort_order.data
            })
            
            # Update policy page metadata
            policy_page.title = form.title.data
            policy_page.slug = form.slug.data
            policy_page.description = form.description.data
            policy_page.is_active = form.is_active.data
            policy_page.show_in_footer = form.show_in_footer.data
            policy_page.sort_order = form.sort_order.data or 0
            
            db.session.commit()
            
            # Audit log the policy page update
            audit_log_update('PolicyPage', policy_page.id, f'Updated policy page: {policy_page.title}', changes)
            
            # Update the files if content changed
            if hasattr(form, 'content') and form.content.data:
                markdown_path = get_secure_policy_page_path(policy_page.markdown_filename)
                html_path = get_secure_policy_page_path(policy_page.html_filename)
                
                if markdown_path and html_path:
                    # Create metadata dictionary and serialize to YAML
                    metadata_dict = {
                        'title': policy_page.title,
                        'slug': policy_page.slug,
                        'description': policy_page.description,
                        'is_active': policy_page.is_active,
                        'show_in_footer': policy_page.show_in_footer,
                        'sort_order': policy_page.sort_order,
                        'author': policy_page.author_id
                    }
                    metadata = "---\n" + yaml.dump(metadata_dict, default_flow_style=False) + "---\n"
                    
                    # Write updated markdown file
                    with open(markdown_path, 'w', encoding='utf-8') as f:
                        f.write(metadata + "\n" + form.content.data)
                    
                    # Convert to HTML and write HTML file
                    html_content = markdown(form.content.data, extras=['fenced-code-blocks', 'tables'])
                    sanitized_html = sanitize_html_content(html_content)
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(sanitized_html)
            
            flash('Policy page updated successfully!', 'success')
            return redirect(url_for('admin.manage_policy_pages'))
        
        # For GET requests, populate form with existing data and content
        if request.method == 'GET':
            markdown_path = get_secure_policy_page_path(policy_page.markdown_filename)
            if markdown_path and os.path.exists(markdown_path):
                with open(markdown_path, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()
                metadata, content = parse_metadata_from_markdown(markdown_content)
                if hasattr(form, 'content'):
                    form.content.data = content
        
        return render_template('admin/policy_page_form.html', form=form, title="Edit Policy Page", policy_page=policy_page)
        
    except Exception as e:
        current_app.logger.error(f"Error in edit_policy_page: {str(e)}")
        flash('An error occurred while editing the policy page.', 'error')
        return redirect(url_for('admin.manage_policy_pages'))


@bp.route('/delete_policy_page/<int:policy_page_id>', methods=['POST'])
@login_required
@role_required('Content Manager')
def delete_policy_page(policy_page_id):
    """
    Admin interface for deleting policy pages
    """
    try:
        from app.utils import get_secure_policy_page_path
        import os
        
        policy_page = db.session.get(PolicyPage, policy_page_id)
        if not policy_page:
            flash('Policy page not found.', 'error')
            return redirect(url_for('admin.manage_policy_pages'))
        
        # Capture policy page info for audit log
        policy_page_info = f'{policy_page.title} (slug: {policy_page.slug})'
        
        # Delete associated files
        markdown_path = get_secure_policy_page_path(policy_page.markdown_filename)
        html_path = get_secure_policy_page_path(policy_page.html_filename)
        
        if markdown_path and os.path.exists(markdown_path):
            os.remove(markdown_path)
        if html_path and os.path.exists(html_path):
            os.remove(html_path)
        
        # Delete from database
        db.session.delete(policy_page)
        db.session.commit()
        
        # Audit log the policy page deletion
        audit_log_delete('PolicyPage', policy_page_id, f'Deleted policy page: {policy_page_info}')
        
        flash('Policy page deleted successfully!', 'success')
        return redirect(url_for('admin.manage_policy_pages'))
        
    except Exception as e:
        current_app.logger.error(f"Error in delete_policy_page: {str(e)}")
        flash('An error occurred while deleting the policy page.', 'error')
        return redirect(url_for('admin.manage_policy_pages'))


@bp.route('/edit_booking/<int:booking_id>', methods=['GET', 'POST'])
@login_required
@role_required('Event Manager')
def edit_booking(booking_id):
    """
    Admin interface for editing existing bookings
    """
    try:
        from app.forms import BookingForm
        from app.utils import get_secure_post_path
        
        booking = db.session.get(Booking, booking_id)
        if not booking:
            flash('Booking not found.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        form = BookingForm(obj=booking)
        
        if form.validate_on_submit():
            # Capture changes for audit log
            changes = get_model_changes(booking, {
                'booking_date': form.booking_date.data,
                'session': form.session.data,
                'rink_count': form.rink_count.data,
                'priority': form.priority.data,
                'vs': form.vs.data,
                'home_away': form.home_away.data
            })
            
            # Update the booking with form data
            booking.booking_date = form.booking_date.data
            booking.session = form.session.data
            booking.rink_count = form.rink_count.data
            booking.priority = form.priority.data
            booking.vs = form.vs.data
            booking.home_away = form.home_away.data
            
            db.session.commit()
            
            # Audit log the booking edit
            audit_log_update('Booking', booking.id, f'Edited booking #{booking.id}', changes)
            
            flash('Booking updated successfully!', 'success')
            
            # Redirect back to events management if the booking has an event
            if booking.event_id:
                return redirect(url_for('admin.manage_events'))
            else:
                return redirect(url_for('main.bookings'))
        
        return render_template('admin/booking_form.html', 
                             form=form, 
                             booking=booking,
                             title=f"Edit Booking #{booking.id}")
        
    except Exception as e:
        current_app.logger.error(f"Error in edit_booking: {str(e)}")
        flash('An error occurred while editing the booking.', 'error')
        return redirect(url_for('admin.manage_events'))


@bp.route('/recover_policy_page/<filename>', methods=['POST'])
@login_required
@admin_required
def recover_policy_page(filename):
    """
    Admin interface for recovering orphaned policy page files
    """
    try:
        from app.utils import recover_orphaned_policy_page
        
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('admin.manage_policy_pages'))
        
        # Attempt to recover the orphaned policy page
        success, message, policy_page = recover_orphaned_policy_page(filename, current_user.id)
        
        if success and policy_page:
            # Audit log the policy page recovery
            audit_log_create('PolicyPage', policy_page.id, 
                            f'Recovered orphaned policy page: {policy_page.title}',
                            {'recovered_from': filename, 'slug': policy_page.slug})
            
            flash(message, 'success')
        else:
            flash(message, 'error')
        
        return redirect(url_for('admin.manage_policy_pages'))
        
    except Exception as e:
        current_app.logger.error(f"Error in recover_policy_page: {str(e)}")
        flash('An error occurred while recovering the policy page.', 'error')
        return redirect(url_for('admin.manage_policy_pages'))


@bp.route('/edit_event_team/<int:team_id>', methods=['GET', 'POST'])
@login_required
@role_required('Event Manager')
def edit_event_team(team_id):
    """
    Admin interface for editing event teams and assigning players to positions
    """
    try:
        from app.models import EventTeam, TeamMember
        from app.forms import create_team_member_form
        
        team = db.session.get(EventTeam, team_id)
        if not team:
            flash('Team not found.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Check if user has permission to manage this event
        if not current_user.is_admin and current_user not in team.event.event_managers:
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Non-authorized user attempted to edit team {team_id}')
            flash('You do not have permission to edit this team.', 'error')
            return redirect(url_for('admin.manage_events', event_id=team.event.id))
        
        TeamMemberForm = create_team_member_form(team.event.format, team.event)
        form = TeamMemberForm()
        
        if form.validate_on_submit():
            try:
                # Capture existing team members for audit log
                existing_members = db.session.scalars(
                    sa.select(TeamMember).where(TeamMember.event_team_id == team.id)
                ).all()
                old_members = [f"{member.member.firstname} {member.member.lastname} ({member.position})" 
                              for member in existing_members]
                
                # Update team name
                old_team_name = team.team_name
                team.team_name = form.team_name.data
                
                # Build new team composition from form data
                team_positions = current_app.config.get('TEAM_POSITIONS', {})
                positions = team_positions.get(team.event.format, [])
                new_team_data = {}
                new_members = []
                
                for position in positions:
                    field_name = f"position_{position.lower().replace(' ', '_')}"
                    member_id = getattr(form, field_name).data
                    
                    if member_id and member_id > 0:  # Skip empty selections
                        new_team_data[position] = member_id
                        member_obj = db.session.get(Member, member_id)
                        if member_obj:
                            new_members.append(f"{member_obj.firstname} {member_obj.lastname} ({position})")
                
                # Only update team members if we have valid new data
                # Clear existing team members ONLY after we know new data is valid
                for member in existing_members:
                    db.session.delete(member)
                
                # Add new team members
                for position, member_id in new_team_data.items():
                    team_member = TeamMember(
                        event_team_id=team.id,
                        member_id=member_id,
                        position=position
                    )
                    db.session.add(team_member)
                
                # Commit all changes together
                db.session.commit()
                
                # Audit log the team update
                changes = {}
                if old_team_name != team.team_name:
                    changes['team_name'] = old_team_name
                changes['old_members'] = old_members
                changes['new_members'] = new_members
                
                audit_log_update('EventTeam', team.id, 
                                f'Updated team: {team.team_name} for event "{team.event.name}"', changes)
                
                flash(f'Team "{team.team_name}" updated successfully!', 'success')
                return redirect(url_for('admin.manage_events', event_id=team.event.id))
                
            except Exception as e:
                # Rollback transaction on any error to preserve existing data
                db.session.rollback()
                current_app.logger.error(f"Error updating team {team.id}: {str(e)}")
                flash('An error occurred while updating the team. No changes were made.', 'error')
        
        # Pre-populate form with existing data
        if request.method == 'GET':
            form.team_id.data = team.id
            form.team_name.data = team.team_name
            
            # Load existing team member assignments
            existing_members = db.session.scalars(
                sa.select(TeamMember).where(TeamMember.event_team_id == team.id)
            ).all()
            
            for member in existing_members:
                field_name = f"position_{member.position.lower().replace(' ', '_')}"
                if hasattr(form, field_name):
                    getattr(form, field_name).data = member.member_id
        
        return render_template('admin/edit_event_team.html', 
                             form=form, 
                             team=team,
                             event=team.event,
                             title=f"Edit {team.team_name}")
        
    except Exception as e:
        current_app.logger.error(f"Error in edit_event_team: {str(e)}")
        current_app.logger.error(f"Full traceback: ", exc_info=True)
        flash('An error occurred while editing the team.', 'error')
        # Try to get event_id from team if possible
        try:
            team = db.session.get(EventTeam, team_id)
            if team:
                return redirect(url_for('admin.manage_events', event_id=team.event_id, stage=3))
        except:
            pass
        return redirect(url_for('admin.manage_events'))


@bp.route('/add_event_team/<int:event_id>', methods=['GET', 'POST'])
@login_required
@role_required('Event Manager')
def add_event_team(event_id):
    """
    Admin interface for adding a new team to an event
    """
    try:
        from app.models import EventTeam
        from app.forms import AddTeamForm
        
        event = db.session.get(Event, event_id)
        if not event:
            flash('Event not found.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Check if user has permission to manage this event
        if not current_user.is_admin and current_user not in event.event_managers:
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Non-authorized user attempted to add team to event {event_id}')
            flash('You do not have permission to manage this event.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        form = AddTeamForm()
        
        if form.validate_on_submit():
            # Get the next team number
            existing_teams = db.session.scalars(
                sa.select(EventTeam).where(EventTeam.event_id == event_id)
            ).all()
            next_team_number = len(existing_teams) + 1
            
            # Create the new team
            new_team = EventTeam(
                event_id=event_id,
                team_name=form.team_name.data,
                team_number=next_team_number
            )
            db.session.add(new_team)
            db.session.commit()
            
            # Audit log the team creation
            audit_log_create('EventTeam', new_team.id, 
                            f'Created team: {new_team.team_name} for event "{event.name}"',
                            {'team_number': next_team_number})
            
            flash(f'Team "{new_team.team_name}" added successfully!', 'success')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        return render_template('admin/add_event_team.html', 
                             form=form, 
                             event=event,
                             title=f"Add Team to {event.name}")
        
    except Exception as e:
        current_app.logger.error(f"Error in add_event_team: {str(e)}")
        flash('An error occurred while adding the team.', 'error')
        return redirect(url_for('admin.manage_events', event_id=event_id))


@bp.route('/delete_event_team/<int:team_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def delete_event_team(team_id):
    """
    Admin interface for deleting an event team
    """
    try:
        from app.models import EventTeam
        
        # Get team first to get event_id for redirects
        team = db.session.get(EventTeam, team_id)
        if not team:
            flash('Team not found.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        event_id = team.event_id
        team_name = team.team_name
        
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Check if user has permission to manage this event
        if not current_user.is_admin and current_user not in team.event.event_managers:
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Non-authorized user attempted to delete team {team_id}')
            flash('You do not have permission to manage this event.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        event_name = team.event.name
        
        # Check if this team has associated booking teams
        booking_teams_count = len(team.booking_teams)
        if booking_teams_count > 0:
            # Get unique bookings that use this team
            affected_bookings = list(set([bt.booking for bt in team.booking_teams]))
            booking_dates = [booking.booking_date.strftime('%Y-%m-%d') for booking in affected_bookings]
            
            flash(f'Warning: Team "{team_name}" is used in {booking_teams_count} booking(s) on {", ".join(booking_dates)}. '
                  f'Deleting this team will not affect existing bookings (they remain independent), '
                  f'but you won\'t be able to trace them back to this template.', 'warning')
        
        # Delete the team (cascade will handle team_members and booking_teams relationship)
        db.session.delete(team)
        db.session.commit()
        
        # Audit log the team deletion
        audit_log_delete('EventTeam', team_id, 
                        f'Deleted team: {team_name} from event "{event_name}"',
                        {'booking_teams_affected': booking_teams_count})
        
        if booking_teams_count > 0:
            flash(f'Team "{team_name}" deleted. Existing bookings remain unchanged.', 'info')
        else:
            flash(f'Team "{team_name}" deleted successfully!', 'success')
        
        return redirect(url_for('admin.manage_events', event_id=event_id))
        
    except Exception as e:
        current_app.logger.error(f"Error in delete_event_team: {str(e)}")
        flash('An error occurred while deleting the team.', 'error')
        # Try to get event_id from team if possible, otherwise redirect without it
        try:
            team = db.session.get(EventTeam, team_id)
            if team:
                return redirect(url_for('admin.manage_events', event_id=team.event_id))
        except:
            pass
        return redirect(url_for('admin.manage_events'))


@bp.route('/create_teams_from_pool/<int:event_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def create_teams_from_pool(event_id):
    """
    Create teams from pool members with 'available' status
    """
    try:
        from app.models import EventTeam, TeamMember
        from app.audit import audit_log_create, audit_log_bulk_operation
        
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        event = db.session.get(Event, event_id)
        if not event or not event.has_pool_enabled():
            flash('Event not found or pool not enabled.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Check if user has permission
        if not current_user.is_admin and current_user not in event.event_managers:
            flash('You do not have permission to manage this event.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Get available pool members
        available_members = event.pool.get_available_members()
        if not available_members:
            flash('No available members in the pool to create teams.', 'warning')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Get team configuration from app config
        team_positions = current_app.config.get('TEAM_POSITIONS', {})
        positions = team_positions.get(event.format, [])
        
        if not positions:
            flash(f'No team positions configured for format: {event.format}', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        team_size = len(positions)
        num_complete_teams = len(available_members) // team_size
        
        if num_complete_teams == 0:
            flash(f'Not enough available members ({len(available_members)}) to create a complete team (need {team_size}).', 'warning')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Get existing team count for numbering
        existing_teams_count = db.session.scalar(
            sa.select(sa.func.count(EventTeam.id)).where(EventTeam.event_id == event_id)
        ) or 0
        
        teams_created = 0
        members_assigned = 0
        
        # Create teams
        for team_num in range(num_complete_teams):
            team_number = existing_teams_count + team_num + 1
            team_name = f"Team {team_number}"
            
            # Create the team
            new_team = EventTeam(
                event_id=event_id,
                team_name=team_name,
                team_number=team_number
            )
            db.session.add(new_team)
            db.session.flush()  # Get team ID
            
            # Assign members to positions
            team_members_info = []
            for i, position in enumerate(positions):
                member_idx = (team_num * team_size) + i
                if member_idx < len(available_members):
                    member = available_members[member_idx]
                    
                    # Create team member assignment
                    team_member = TeamMember(
                        event_team_id=new_team.id,
                        member_id=member.id,
                        position=position
                    )
                    db.session.add(team_member)
                    
                    # Update pool registration status to 'selected'
                    pool_registration = event.pool.get_member_registration(member.id)
                    if pool_registration:
                        pool_registration.set_selected()
                    
                    team_members_info.append(f"{member.firstname} {member.lastname} ({position})")
                    members_assigned += 1
            
            teams_created += 1
            
            # Audit log each team creation
            audit_log_create('EventTeam', new_team.id, 
                            f'Created team from pool: {team_name} for event "{event.name}"',
                            {'members': team_members_info, 'created_from_pool': True})
        
        # Commit all changes
        db.session.commit()
        
        # Audit log bulk operation
        audit_log_bulk_operation('TEAM_CREATION_FROM_POOL', 'EventTeam', teams_created,
                                f'Created {teams_created} teams from pool for event "{event.name}"',
                                {'members_assigned': members_assigned, 'event_id': event_id})
        
        remaining_members = len(available_members) - members_assigned
        message = f'Successfully created {teams_created} teams with {members_assigned} members assigned.'
        if remaining_members > 0:
            message += f' {remaining_members} members remain available in the pool.'
        
        flash(message, 'success')
        return redirect(url_for('admin.manage_events', event_id=event_id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating teams from pool: {str(e)}")
        flash('An error occurred while creating teams from the pool.', 'error')
        return redirect(url_for('admin.manage_events'))


@bp.route('/bulk_update_pool_status/<int:event_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def bulk_update_pool_status(event_id):
    """
    Bulk update pool member statuses (e.g., mark all as available)
    """
    try:
        from app.audit import audit_log_bulk_operation
        
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        event = db.session.get(Event, event_id)
        if not event or not event.has_pool_enabled():
            flash('Event not found or pool not enabled.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Check permission
        if not current_user.is_admin and current_user not in event.event_managers:
            flash('You do not have permission to manage this event.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        action = request.form.get('action')
        if action not in ['mark_all_available', 'clear_selections']:
            flash('Invalid action.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        registrations = event.pool.registrations
        updated_count = 0
        
        if action == 'mark_all_available':
            # Mark all registered members as available
            for registration in registrations:
                if registration.status == 'registered':
                    registration.set_available()
                    updated_count += 1
        
        elif action == 'clear_selections':
            # Reset all selected members back to available
            for registration in registrations:
                if registration.status == 'selected':
                    registration.set_available()
                    updated_count += 1
        
        db.session.commit()
        
        # Audit log
        audit_log_bulk_operation('POOL_STATUS_UPDATE', 'PoolRegistration', updated_count,
                                f'Bulk {action} for event "{event.name}"',
                                {'event_id': event_id, 'action': action})
        
        flash(f'Updated {updated_count} pool member statuses.', 'success')
        return redirect(url_for('admin.manage_events', event_id=event_id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in bulk pool update: {str(e)}")
        flash('An error occurred while updating pool statuses.', 'error')
        return redirect(url_for('admin.manage_events'))


@bp.route('/copy_teams_to_booking/<int:event_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def copy_teams_to_booking(event_id):
    """
    Create a booking from event teams (Stage 5: Booking system redesign)
    """
    try:
        from app.models import EventTeam, BookingTeam, BookingTeamMember, Booking
        from app.forms import BookingForm
        from app.audit import audit_log_create, audit_log_bulk_operation
        import json
        
        # Get form data
        booking_date = request.form.get('booking_date')
        session = request.form.get('session', type=int)
        vs = request.form.get('vs', '')
        home_away = request.form.get('home_away', 'home')
        priority = request.form.get('priority', '')
        
        if not booking_date or not session:
            flash('Booking date and session are required.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Parse date
        from datetime import datetime
        try:
            booking_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        event = db.session.get(Event, event_id)
        if not event:
            flash('Event not found.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Check if user has permission
        if not current_user.is_admin and current_user not in event.event_managers:
            flash('You do not have permission to manage this event.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Get event teams
        event_teams = db.session.scalars(
            sa.select(EventTeam).where(EventTeam.event_id == event_id)
            .order_by(EventTeam.team_number)
        ).all()
        
        if not event_teams:
            flash('No teams found for this event.', 'warning')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Create the booking
        new_booking = Booking(
            booking_date=booking_date,
            session=session,
            organizer_id=current_user.id,
            rink_count=len(event_teams),  # One rink per team
            booking_type='event',
            priority=priority,
            vs=vs,
            home_away=home_away,
            event_id=event_id
        )
        
        db.session.add(new_booking)
        db.session.flush()  # Get booking ID
        
        teams_copied = 0
        members_copied = 0
        
        # Copy each event team to booking team
        for event_team in event_teams:
            # Create booking team
            booking_team = BookingTeam(
                booking_id=new_booking.id,
                event_team_id=event_team.id,
                team_name=event_team.team_name,
                team_number=event_team.team_number
            )
            db.session.add(booking_team)
            db.session.flush()  # Get booking team ID
            
            # Copy team members
            for team_member in event_team.team_members:
                booking_team_member = BookingTeamMember(
                    booking_team_id=booking_team.id,
                    member_id=team_member.member_id,
                    position=team_member.position,
                    is_substitute=False,
                    availability_status='pending'
                )
                db.session.add(booking_team_member)
                members_copied += 1
            
            teams_copied += 1
        
        # Commit all changes
        db.session.commit()
        
        # Audit logging
        audit_log_create('Booking', new_booking.id, 
                        f'Created booking from event teams for {event.name} on {booking_date}',
                        {'teams_copied': teams_copied, 'members_copied': members_copied, 
                         'vs': vs, 'home_away': home_away})
        
        audit_log_bulk_operation('TEAM_TO_BOOKING_COPY', 'BookingTeam', teams_copied,
                                f'Copied {teams_copied} teams to booking for {event.name}',
                                {'booking_id': new_booking.id, 'event_id': event_id})
        
        flash(f'Successfully created booking with {teams_copied} teams and {members_copied} members.', 'success')
        return redirect(url_for('admin.manage_events', event_id=event_id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error copying teams to booking: {str(e)}")
        flash('An error occurred while creating the booking.', 'error')
        return redirect(url_for('admin.manage_events'))


@bp.route('/add_substitute_to_team/<int:booking_team_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def add_substitute_to_team(booking_team_id):
    """
    Add a substitute to a booking team
    """
    try:
        from app.models import BookingTeam, BookingTeamMember
        from app.audit import audit_log_create
        
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        booking_team = db.session.get(BookingTeam, booking_team_id)
        if not booking_team:
            flash('Team not found.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        member_id = request.form.get('member_id', type=int)
        position = request.form.get('position', '')
        
        if not member_id or not position:
            flash('Member and position are required.', 'error')
            return redirect(url_for('admin.manage_events', event_id=booking_team.booking.event_id))
        
        # Check if member is already in the team
        existing = db.session.scalar(
            sa.select(BookingTeamMember).where(
                BookingTeamMember.booking_team_id == booking_team_id,
                BookingTeamMember.member_id == member_id
            )
        )
        
        if existing:
            flash('Member is already in this team.', 'warning')
            return redirect(url_for('admin.manage_events', event_id=booking_team.booking.event_id))
        
        # Add substitute
        substitute = BookingTeamMember(
            booking_team_id=booking_team_id,
            member_id=member_id,
            position=position,
            is_substitute=True,
            availability_status='pending'
        )
        
        db.session.add(substitute)
        db.session.commit()
        
        # Get member name for feedback
        member = db.session.get(Member, member_id)
        member_name = f"{member.firstname} {member.lastname}" if member else "Unknown"
        
        # Audit log
        audit_log_create('BookingTeamMember', substitute.id,
                        f'Added substitute {member_name} to team {booking_team.team_name}',
                        {'position': position, 'is_substitute': True})
        
        flash(f'Added {member_name} as substitute {position} to {booking_team.team_name}.', 'success')
        return redirect(url_for('admin.manage_events', event_id=booking_team.booking.event_id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding substitute: {str(e)}")
        flash('An error occurred while adding the substitute.', 'error')
        return redirect(url_for('admin.manage_events'))


@bp.route('/update_member_availability/<int:booking_team_member_id>', methods=['POST'])
@login_required
def update_member_availability(booking_team_member_id):
    """
    Update a team member's availability status (accessible to team members and admins)
    """
    try:
        from app.models import BookingTeamMember
        from app.audit import audit_log_update
        
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('main.index'))
        
        booking_team_member = db.session.get(BookingTeamMember, booking_team_member_id)
        if not booking_team_member:
            flash('Team member not found.', 'error')
            return redirect(url_for('main.index'))
        
        # Check permission - member can update their own availability
        if not current_user.is_admin and current_user.id != booking_team_member.member_id:
            flash('You can only update your own availability.', 'error')
            return redirect(url_for('main.index'))
        
        new_status = request.form.get('status')
        if new_status not in ['pending', 'available', 'unavailable']:
            flash('Invalid status.', 'error')
            return redirect(url_for('main.index'))
        
        old_status = booking_team_member.availability_status
        booking_team_member.availability_status = new_status
        
        if new_status != 'pending':
            booking_team_member.confirmed_at = datetime.utcnow()
        
        db.session.commit()
        
        # Audit log
        audit_log_update('BookingTeamMember', booking_team_member.id,
                        f'Availability updated from {old_status} to {new_status}',
                        {'old_status': old_status, 'new_status': new_status})
        
        flash(f'Availability updated to {new_status}.', 'success')
        return redirect(url_for('main.index'))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating availability: {str(e)}")
        flash('An error occurred while updating availability.', 'error')
        return redirect(url_for('main.index'))


@bp.route('/auto_select_pool_members/<int:event_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def auto_select_pool_members(event_id):
    """
    Automatically select pool members for team creation based on criteria
    """
    try:
        from app.audit import audit_log_bulk_operation
        
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        event = db.session.get(Event, event_id)
        if not event or not event.has_pool_enabled():
            flash('Event not found or pool not enabled.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Check permission
        if not current_user.is_admin and current_user not in event.event_managers:
            flash('You do not have permission to manage this event.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        selection_method = request.form.get('method', 'oldest_first')
        num_to_select = request.form.get('count', type=int)
        
        if not num_to_select or num_to_select <= 0:
            flash('Invalid selection count.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Get registered members
        registered_members = [reg for reg in event.pool.registrations if reg.status == 'registered']
        
        if len(registered_members) < num_to_select:
            flash(f'Only {len(registered_members)} registered members available, cannot select {num_to_select}.', 'warning')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Apply selection method
        if selection_method == 'oldest_first':
            selected_registrations = sorted(registered_members, key=lambda r: r.registered_at)[:num_to_select]
        elif selection_method == 'random':
            import random
            selected_registrations = random.sample(registered_members, num_to_select)
        else:
            # Default to oldest first
            selected_registrations = sorted(registered_members, key=lambda r: r.registered_at)[:num_to_select]
        
        # Update selected members to 'available' status
        updated_count = 0
        for registration in selected_registrations:
            registration.set_available()
            updated_count += 1
        
        db.session.commit()
        
        # Audit log
        audit_log_bulk_operation('AUTO_POOL_SELECTION', 'PoolRegistration', updated_count,
                                f'Auto-selected {updated_count} members using {selection_method} for {event.name}',
                                {'event_id': event_id, 'method': selection_method})
        
        flash(f'Automatically selected {updated_count} members for team creation.', 'success')
        return redirect(url_for('admin.manage_events', event_id=event_id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in auto pool selection: {str(e)}")
        flash('An error occurred during automatic selection.', 'error')
        return redirect(url_for('admin.manage_events'))


@bp.route('/manage_teams/<int:booking_id>', methods=['GET', 'POST'])
@login_required
@role_required('Event Manager')
def manage_teams(booking_id):
    """
    Admin interface for managing teams for a specific booking
    Accessible to admins and booking organizers
    """
    try:
        # Get the booking
        booking = db.session.get(Booking, booking_id)
        if not booking:
            flash('Booking not found.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Check if user has permission to manage teams
        if not current_user.is_admin and booking.organizer_id != current_user.id:
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized attempt to manage teams for booking {booking_id}')
            flash('You do not have permission to manage teams for this booking.', 'error')
            return redirect(url_for('main.bookings'))
        
        from app.models import BookingTeam, BookingTeamMember
        
        # Get existing teams for this booking
        teams = db.session.scalars(
            sa.select(BookingTeam)
            .where(BookingTeam.booking_id == booking_id)
            .order_by(BookingTeam.team_name)
        ).all()
        
        # Handle POST request for team management
        if request.method == 'POST':
            csrf_form = FlaskForm()
            if not csrf_form.validate_on_submit():
                flash('Security validation failed.', 'error')
                return redirect(url_for('admin.manage_teams', booking_id=booking_id))
            
            # Handle different actions
            action = request.form.get('action')
            
            if action == 'add_team':
                team_name = request.form.get('team_name')
                if team_name:
                    new_team = BookingTeam(
                        booking_id=booking_id,
                        team_name=team_name,
                        event_team_id=booking.event.teams[0].id if booking.event and booking.event.teams else None
                    )
                    db.session.add(new_team)
                    db.session.commit()
                    
                    audit_log_create('BookingTeam', new_team.id, 
                                   f'Added team {team_name} to booking {booking_id}')
                    flash(f'Team "{team_name}" added successfully.', 'success')
                else:
                    flash('Team name is required.', 'error')
            
            return redirect(url_for('admin.manage_teams', booking_id=booking_id))
        
        # Get session name
        sessions = current_app.config.get('DAILY_SESSIONS', {})
        session_name = sessions.get(booking.session, 'Unknown Session')
        
        # Create CSRF form for template
        csrf_form = FlaskForm()
        
        return render_template('admin/manage_teams.html', 
                             booking=booking,
                             teams=teams,
                             session_name=session_name,
                             csrf_form=csrf_form)
        
    except Exception as e:
        current_app.logger.error(f"Error managing teams for booking {booking_id}: {str(e)}")
        flash('An error occurred while managing teams.', 'error')
        return redirect(url_for('main.bookings'))


@bp.route('/add_user_to_role', methods=['POST'])
@login_required
@role_required('User Manager')
def add_user_to_role():
    """
    Add a user to a role (AJAX endpoint)
    """
    try:
        from app.models import Role
        import json
        
        data = request.get_json()
        user_id = data.get('user_id')
        role_id = data.get('role_id')
        
        if not user_id or not role_id:
            return jsonify({
                'success': False,
                'error': 'User ID and Role ID are required'
            }), 400
        
        # Get user and role
        user = db.session.get(Member, user_id)
        role = db.session.get(Role, role_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
            
        if not role:
            return jsonify({
                'success': False,
                'error': 'Role not found'
            }), 404
        
        # Check if user already has this role
        if role in user.roles:
            return jsonify({
                'success': False,
                'error': 'User already has this role'
            }), 400
        
        # Add role to user
        user.roles.append(role)
        db.session.commit()
        
        # Audit log
        audit_log_update('Member', user.id, 
                        f'Added role "{role.name}" to user {user.firstname} {user.lastname}',
                        {'action': 'add_role', 'role_name': role.name})
        
        return jsonify({
            'success': True,
            'message': f'Role "{role.name}" added to {user.firstname} {user.lastname}'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding user to role: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while adding the user to the role'
        }), 500


@bp.route('/remove_user_from_role', methods=['POST'])
@login_required
@role_required('User Manager')
def remove_user_from_role():
    """
    Remove a user from a role (AJAX endpoint)
    """
    try:
        from app.models import Role
        import json
        
        data = request.get_json()
        user_id = data.get('user_id')
        role_id = data.get('role_id')
        
        if not user_id or not role_id:
            return jsonify({
                'success': False,
                'error': 'User ID and Role ID are required'
            }), 400
        
        # Get user and role
        user = db.session.get(Member, user_id)
        role = db.session.get(Role, role_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
            
        if not role:
            return jsonify({
                'success': False,
                'error': 'Role not found'
            }), 404
        
        # Check if user has this role
        if role not in user.roles:
            return jsonify({
                'success': False,
                'error': 'User does not have this role'
            }), 400
        
        # Remove role from user
        user.roles.remove(role)
        db.session.commit()
        
        # Audit log
        audit_log_update('Member', user.id, 
                        f'Removed role "{role.name}" from user {user.firstname} {user.lastname}',
                        {'action': 'remove_role', 'role_name': role.name})
        
        return jsonify({
            'success': True,
            'message': f'Role "{role.name}" removed from {user.firstname} {user.lastname}'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error removing user from role: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while removing the user from the role'
        }), 500


@bp.route('/add_member_to_pool/<int:event_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def add_member_to_pool(event_id):
    """
    Add a member to the event pool (for Event Managers to expand the pool)
    """
    try:
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Get the event
        event = db.session.get(Event, event_id)
        if not event:
            flash('Event not found.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Check if event has pool enabled
        if not event.has_pool_enabled():
            flash('This event does not have pool registration enabled.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Get member_id from form
        member_id = request.form.get('member_id', type=int)
        if not member_id:
            flash('Please select a member to add.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Get the member
        member = db.session.get(Member, member_id)
        if not member:
            flash('Member not found.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Check if member is already in the pool
        existing_registration = event.pool.get_member_registration(member_id)
        if existing_registration and existing_registration.is_active:
            flash(f'{member.firstname} {member.lastname} is already registered for this event.', 'warning')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Add member to pool
        registration = PoolRegistration(
            pool_id=event.pool.id,
            member_id=member_id,
            status='available'  # Event Manager added, so mark as available
        )
        db.session.add(registration)
        db.session.commit()
        
        # Audit log
        audit_log_create('PoolRegistration', registration.id, 
                        f'Event Manager added {member.firstname} {member.lastname} to pool for event: {event.name}')
        
        flash(f'{member.firstname} {member.lastname} added to event pool successfully!', 'success')
        return redirect(url_for('admin.manage_events', event_id=event_id))
        
    except Exception as e:
        current_app.logger.error(f"Error adding member to pool: {str(e)}")
        flash('An error occurred while adding member to pool.', 'error')
        return redirect(url_for('admin.manage_events', event_id=event_id))


@bp.route('/test')
@login_required
@admin_required
def test():
    return "Admin routes are working!"