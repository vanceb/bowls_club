# Content routes for the Bowls Club application
from datetime import datetime, timedelta, date
from flask import render_template, flash, redirect, url_for, request, current_app, jsonify
from flask_login import login_required, current_user
import sqlalchemy as sa
import os

from app.content import bp
from app import db
from app.models import Post, PolicyPage
from app.audit import audit_log_create, audit_log_update, audit_log_delete, audit_log_security_event, get_model_changes
from app.content.forms import WritePostForm, PolicyPageForm
from app.content.utils import (
    generate_secure_filename, get_secure_post_path, sanitize_html_content,
    get_secure_policy_page_path, get_secure_archive_path, parse_metadata_from_markdown,
    find_orphaned_policy_pages, recover_orphaned_policy_page
)
from app.routes import role_required, admin_required
from app.forms import FlaskForm

@bp.route('/admin/write_post', methods=['GET', 'POST'])
@login_required
@role_required('Content Manager')
def admin_write_post():
    """
    Admin interface for writing posts
    """
    try:
        from app.content.forms import WritePostForm
        
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
                return render_template('admin_write_post.html', form=form)
            
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
                    return render_template('admin_write_post.html', form=form)
                
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
                import markdown2
                html_content = markdown2.markdown(content, extras=['fenced-code-blocks', 'tables', 'header-ids', 'code-friendly'])
                sanitized_html = sanitize_html_content(html_content)
                
                with open(html_path, 'w', encoding='utf-8') as html_file:
                    html_file.write(sanitized_html)
                
                # Audit log the post creation
                audit_log_create('Post', post.id, f'Created post: {title}',
                               {'publish_on': publish_on.isoformat(), 'expires_on': expires_on.isoformat()})
                
                flash('Post created successfully!', 'success')
                return redirect(url_for('content.admin_manage_posts'))
                
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error creating post: {str(e)}")
                flash('An error occurred while creating the post.', 'error')
                return render_template('admin_write_post.html', form=form)
        
        # GET request - render form
        return render_template('admin_write_post.html', form=form)
        
    except Exception as e:
        current_app.logger.error(f"Error in write_post: {str(e)}")
        flash('An error occurred while loading the write post page.', 'error')
        return redirect(url_for('main.index'))


@bp.route('/admin/manage_posts', methods=['GET', 'POST'])
@login_required
@role_required('Content Manager')
def admin_manage_posts():
    """
    Admin interface for managing posts with bulk operations
    """
    try:
        import shutil
        
        today = date.today()
        posts_query = sa.select(Post).order_by(Post.created_at.desc())
        posts = db.session.scalars(posts_query).all()

        if request.method == 'POST':
            # Validate CSRF token
            csrf_form = FlaskForm()
            if not csrf_form.validate_on_submit():
                flash('Security validation failed.', 'error')
                return redirect(url_for('content.admin_manage_posts'))
                
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
            return redirect(url_for('content.admin_manage_posts'))

        # Create a simple form for CSRF protection
        csrf_form = FlaskForm()
        
        return render_template('admin_manage_posts.html', 
                             posts=posts, 
                             today=today,
                             csrf_form=csrf_form)
        
    except Exception as e:
        current_app.logger.error(f"Error in manage_posts: {str(e)}")
        flash('An error occurred while loading posts.', 'error')
        return redirect(url_for('main.index'))


@bp.route('/admin/edit_post/<int:post_id>', methods=['GET', 'POST'])
@login_required
@role_required('Content Manager')
def admin_edit_post(post_id):
    """
    Admin interface for editing posts
    """
    try:
        from app.content.forms import WritePostForm
        import yaml
        import os
        
        current_app.logger.info(f"Edit post request for post_id: {post_id}")
        
        post = db.session.get(Post, post_id)
        if not post:
            current_app.logger.error(f"Post not found with ID: {post_id}")
            flash('Post not found.', 'error')
            return redirect(url_for('content.admin_manage_posts'))

        current_app.logger.info(f"Found post: {post.title}, markdown: {post.markdown_filename}")

        # Load the post content from secure storage
        markdown_path = get_secure_post_path(post.markdown_filename)
        html_path = get_secure_post_path(post.html_filename)
        
        current_app.logger.info(f"Markdown path: {markdown_path}")
        current_app.logger.info(f"HTML path: {html_path}")
        
        if not markdown_path or not html_path:
            current_app.logger.error(f"Could not get secure paths for post files")
            flash('Post file paths could not be determined.', 'error')
            return redirect(url_for('content.admin_manage_posts'))
            
        if not os.path.exists(markdown_path):
            current_app.logger.error(f"Markdown file does not exist: {markdown_path}")
            flash('Post markdown file not found.', 'error')
            return redirect(url_for('content.admin_manage_posts'))

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
            import markdown2
            updated_html = markdown2.markdown(form.content.data, extras=['fenced-code-blocks', 'tables', 'header-ids', 'code-friendly'])
            with open(html_path, 'w') as file:
                file.write(updated_html)

            # Save changes to the database
            db.session.commit()
            
            # Audit log the post update
            audit_log_update('Post', post.id, f'Updated post: {post.title}', changes)
            
            flash("Post updated successfully!", "success")
            return redirect(url_for('content.admin_manage_posts'))

        # Create CSRF form for template
        csrf_form = FlaskForm()
        return render_template('admin_write_post.html', form=form, post=post, csrf_form=csrf_form)
        
    except Exception as e:
        current_app.logger.error(f"Error in edit_post: {str(e)}")
        flash('An error occurred while editing the post.', 'error')
        return redirect(url_for('content.admin_manage_posts'))


@bp.route('/admin/delete_post/<int:post_id>', methods=['POST'])
@login_required
@role_required('Content Manager')
def admin_delete_post(post_id):
    """
    Admin interface for deleting posts
    """
    try:
        import os
        import shutil
        
        post = db.session.get(Post, post_id)
        if not post:
            flash('Post not found.', 'error')
            return redirect(url_for('content.admin_manage_posts'))

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
        return redirect(url_for('content.admin_manage_posts'))
        
    except Exception as e:
        current_app.logger.error(f"Error in delete_post: {str(e)}")
        flash('An error occurred while deleting the post.', 'error')
        return redirect(url_for('content.admin_manage_posts'))


@bp.route('/admin/manage_policy_pages')
@login_required
@role_required('Content Manager')
def admin_manage_policy_pages():
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
            orphaned_pages = find_orphaned_policy_pages()
            
            # Provide feedback message if no orphaned files found
            if not orphaned_pages:
                flash('No orphaned policy page files found! All files are properly tracked in the database.', 'success')
        
        # Create a simple form for CSRF protection
        csrf_form = FlaskForm()
        
        return render_template('admin_manage_policy_pages.html', 
                             policy_pages=policy_pages, 
                             csrf_form=csrf_form,
                             show_orphaned=show_orphaned,
                             orphaned_pages=orphaned_pages)
        
    except Exception as e:
        current_app.logger.error(f"Error in manage_policy_pages: {str(e)}")
        flash('An error occurred while loading policy pages.', 'error')
        return redirect(url_for('main.index'))


@bp.route('/admin/create_policy_page', methods=['GET', 'POST'])
@login_required
@role_required('Content Manager')
def admin_create_policy_page():
    """
    Admin interface for creating policy pages
    """
    try:
        from app.content.forms import PolicyPageForm
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
                return render_template('admin_policy_page_form.html', form=form, title="Create Policy Page")
            
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
                return render_template('admin_policy_page_form.html', form=form, title="Create Policy Page")
            
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
            import markdown2
            html_content = markdown2.markdown(form.content.data, extras=['fenced-code-blocks', 'tables', 'header-ids', 'code-friendly'])
            sanitized_html = sanitize_html_content(html_content)
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(sanitized_html)
            
            flash('Policy page created successfully!', 'success')
            return redirect(url_for('content.admin_manage_policy_pages'))
        
        return render_template('admin_policy_page_form.html', form=form, title="Create Policy Page")
        
    except Exception as e:
        current_app.logger.error(f"Error in create_policy_page: {str(e)}")
        flash('An error occurred while creating the policy page.', 'error')
        return redirect(url_for('content.admin_manage_policy_pages'))


@bp.route('/admin/edit_policy_page/<int:policy_page_id>', methods=['GET', 'POST'])
@login_required
@role_required('Content Manager')
def admin_edit_policy_page(policy_page_id):
    """
    Admin interface for editing policy pages
    """
    try:
        from app.content.forms import PolicyPageForm
        import yaml
        import os
        from markdown2 import markdown
        
        policy_page = db.session.get(PolicyPage, policy_page_id)
        if not policy_page:
            flash('Policy page not found.', 'error')
            return redirect(url_for('content.admin_manage_policy_pages'))
        
        form = PolicyPageForm(obj=policy_page)
        
        if form.validate_on_submit():
            # Check if slug already exists (but not for this page)
            existing_page = db.session.scalar(
                sa.select(PolicyPage).where(PolicyPage.slug == form.slug.data, PolicyPage.id != policy_page_id)
            )
            if existing_page:
                flash('A policy page with this URL slug already exists. Please choose a different slug.', 'error')
                return render_template('admin_policy_page_form.html', form=form, title="Edit Policy Page")
            
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
                    import markdown2
                    html_content = markdown2.markdown(form.content.data, extras=['fenced-code-blocks', 'tables', 'header-ids', 'code-friendly'])
                    sanitized_html = sanitize_html_content(html_content)
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(sanitized_html)
            
            flash('Policy page updated successfully!', 'success')
            return redirect(url_for('content.admin_manage_policy_pages'))
        
        # For GET requests, populate form with existing data and content
        if request.method == 'GET':
            markdown_path = get_secure_policy_page_path(policy_page.markdown_filename)
            if markdown_path and os.path.exists(markdown_path):
                with open(markdown_path, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()
                metadata, content = parse_metadata_from_markdown(markdown_content)
                if hasattr(form, 'content'):
                    form.content.data = content
        
        return render_template('admin_policy_page_form.html', form=form, title="Edit Policy Page", policy_page=policy_page)
        
    except Exception as e:
        current_app.logger.error(f"Error in edit_policy_page: {str(e)}")
        flash('An error occurred while editing the policy page.', 'error')
        return redirect(url_for('content.admin_manage_policy_pages'))


@bp.route('/admin/delete_policy_page/<int:policy_page_id>', methods=['POST'])
@login_required
@role_required('Content Manager')
def admin_delete_policy_page(policy_page_id):
    """
    Admin interface for deleting policy pages
    """
    try:
        import os
        
        policy_page = db.session.get(PolicyPage, policy_page_id)
        if not policy_page:
            flash('Policy page not found.', 'error')
            return redirect(url_for('content.admin_manage_policy_pages'))
        
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
        return redirect(url_for('content.admin_manage_policy_pages'))
        
    except Exception as e:
        current_app.logger.error(f"Error in delete_policy_page: {str(e)}")
        flash('An error occurred while deleting the policy page.', 'error')
        return redirect(url_for('content.admin_manage_policy_pages'))


@bp.route('/admin/recover_policy_page/<filename>', methods=['POST'])
@login_required
@admin_required
def admin_recover_policy_page(filename):
    """
    Admin interface for recovering orphaned policy page files
    """
    try:
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('content.admin_manage_policy_pages'))
        
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
        
        return redirect(url_for('content.admin_manage_policy_pages'))
        
    except Exception as e:
        current_app.logger.error(f"Error in recover_policy_page: {str(e)}")
        flash('An error occurred while recovering the policy page.', 'error')
        return redirect(url_for('content.admin_manage_policy_pages'))


# Public content viewing routes

@bp.route("/post/<int:post_id>")
@login_required
def view_post(post_id):
    """
    Display a single post with full content
    """
    try:
        from flask import abort
        
        # Get post by ID
        post = db.session.get(Post, post_id)
        if not post:
            current_app.logger.error(f"Post not found with ID: {post_id}")
            abort(404)
        
        current_app.logger.info(f"Found post: {post.title}, HTML file: {post.html_filename}")
        
        # Get the HTML content from secure storage using utility function
        html_path = get_secure_post_path(post.html_filename)
        
        if not html_path:
            current_app.logger.error(f"Could not get secure path for HTML file: {post.html_filename}")
            abort(404)
            
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except FileNotFoundError:
            current_app.logger.error(f"Post HTML file not found: {html_path}")
            abort(404)
        except Exception as e:
            current_app.logger.error(f"Error reading HTML file {html_path}: {str(e)}")
            abort(500)
        
        # Sanitize HTML content
        try:
            sanitized_content = sanitize_html_content(html_content)
        except Exception as e:
            current_app.logger.error(f"Error sanitizing HTML content: {str(e)}")
            sanitized_content = html_content  # Fallback to unsanitized content
        
        return render_template('view_post.html', post=post, content=sanitized_content)
        
    except Exception as e:
        current_app.logger.error(f"Error displaying post {post_id}: {str(e)}")
        abort(500)


@bp.route('/policy/<slug>')
@login_required
def view_policy(slug):
    """
    Display a policy page by slug
    """
    try:
        from flask import abort
        
        # Get policy page by slug
        policy_page = db.session.scalar(
            sa.select(PolicyPage)
            .where(PolicyPage.slug == slug, PolicyPage.is_active == True)
        )
        
        if not policy_page:
            abort(404)
        
        # Get the HTML content from file
        html_path = get_secure_policy_page_path(policy_page.html_filename)
        if not html_path:
            abort(404)
        
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except FileNotFoundError:
            abort(404)
        
        # Sanitize HTML content
        sanitized_content = sanitize_html_content(html_content)
        
        return render_template('view_policy_page.html', 
                             policy_page=policy_page, 
                             content=sanitized_content)
    except Exception as e:
        current_app.logger.error(f"Error displaying policy {slug}: {str(e)}")
        abort(500)