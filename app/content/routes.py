# Content routes for the Bowls Club application
from datetime import datetime, timedelta, date
from flask import render_template, flash, redirect, url_for, request, current_app, jsonify, abort
from flask_login import login_required, current_user
import sqlalchemy as sa
import os

from app.content import bp
from app import db
from app.models import Post, PolicyPage
from app.audit import audit_log_create, audit_log_update, audit_log_delete, audit_log_security_event, get_model_changes
from app.content.forms import WritePostForm, PolicyPageForm
from app.content.utils import (
    create_post_directory, get_post_file_path, get_post_image_path, rename_post_directory,
    sanitize_html_content, get_secure_policy_page_path, get_secure_archive_path, 
    parse_metadata_from_markdown, find_orphaned_policy_pages, recover_orphaned_policy_page
)
from app.routes import role_required, admin_required
from app.forms import FlaskForm


def handle_image_uploads(image_files, post):
    """
    Handle multiple image uploads for a post using directory-based storage
    
    Args:
        image_files: List of uploaded image files
        post: Post object with directory_name set
        
    Returns:
        list: List of uploaded image info dictionaries
    """
    uploaded_images = []
    
    if not post.directory_name:
        current_app.logger.error(f"Post {post.id} has no directory_name set")
        return uploaded_images
    
    try:
        current_app.logger.info(f"Starting image upload handling for post {post.id} in directory {post.directory_name}")
        current_app.logger.info(f"Number of image files received: {len(image_files) if image_files else 0}")
        
        for i, image_file in enumerate(image_files):
            current_app.logger.info(f"Processing image {i+1}: {image_file.filename if image_file else 'None'}")
            
            if image_file and image_file.filename:
                current_app.logger.info(f"Image file details: name={image_file.filename}, content_type={getattr(image_file, 'content_type', 'unknown')}")
                
                # Validate file type
                if not allowed_image_file(image_file.filename):
                    current_app.logger.warning(f'Invalid file type for {image_file.filename}')
                    flash(f'Invalid file type for {image_file.filename}. Only JPEG and PNG are allowed.', 'error')
                    continue
                    
                # Validate file size
                image_file.seek(0, os.SEEK_END)  # Go to end of file
                file_size = image_file.tell()
                image_file.seek(0)  # Reset file position
                current_app.logger.info(f"File size: {file_size} bytes")
                
                max_size = current_app.config.get('IMAGE_MAX_SIZE_MB', 10) * 1024 * 1024
                if file_size > max_size:
                    current_app.logger.warning(f'File {image_file.filename} too large: {file_size} bytes')
                    flash(f'File {image_file.filename} is too large. Maximum size is {current_app.config.get("IMAGE_MAX_SIZE_MB", 10)}MB.', 'error')
                    continue
                
                # Use original filename for now (can add UUID prefix later if needed)
                secure_filename = image_file.filename
                current_app.logger.info(f"Using filename: {secure_filename}")
                
                # Get secure path for image file
                file_path = get_post_image_path(post.directory_name, secure_filename)
                if not file_path:
                    current_app.logger.error(f"Could not get secure path for image {secure_filename} in directory {post.directory_name}")
                    continue
                
                current_app.logger.info(f"Saving file to: {file_path}")
                
                try:
                    image_file.save(file_path)
                    current_app.logger.info(f"File saved successfully to {file_path}")
                    
                    # Check if file actually exists
                    if os.path.exists(file_path):
                        file_size_on_disk = os.path.getsize(file_path)
                        current_app.logger.info(f"File exists on disk with size: {file_size_on_disk} bytes")
                        
                        uploaded_images.append({
                            'filename': secure_filename,
                            'original_name': image_file.filename,
                            'size': file_size_on_disk
                        })
                        current_app.logger.info(f"Added image to uploaded_images: {secure_filename}")
                    else:
                        current_app.logger.error(f"File does not exist after save: {file_path}")
                        continue
                        
                except Exception as save_error:
                    current_app.logger.error(f"Error saving file {image_file.filename}: {str(save_error)}")
                    continue
                    
            else:
                current_app.logger.info(f"Skipping empty image file at index {i}")
    
    except Exception as e:
        current_app.logger.error(f"Error handling image uploads: {str(e)}")
        import traceback
        current_app.logger.error(f"Full traceback: {traceback.format_exc()}")
        flash('An error occurred while uploading images.', 'error')
    
    current_app.logger.info(f"Image upload handling completed. Processed {len(uploaded_images)} images")
    return uploaded_images


def allowed_image_file(filename):
    """Check if filename has an allowed image extension"""
    if not filename or '.' not in filename:
        return False
    
    ext = filename.rsplit('.', 1)[1].lower()
    allowed_types = current_app.config.get('IMAGE_ALLOWED_TYPES', ['jpg', 'jpeg', 'png'])
    return ext in allowed_types


def cleanup_abandoned_drafts():
    """
    Clean up draft posts that are older than 24 hours and haven't been updated
    This can be called from a cron job or scheduled task
    """
    try:
        import shutil
        
        # Find draft posts older than 24 hours
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        abandoned_drafts = db.session.scalars(
            sa.select(Post).where(
                Post.is_draft == True,
                Post.created_at < cutoff_time
            )
        ).all()
        
        deleted_count = 0
        for draft in abandoned_drafts:
            try:
                # Remove entire post directory (includes images, markdown, and html files)
                if draft.directory_name:
                    post_dir = os.path.join(current_app.config['POSTS_STORAGE_PATH'], draft.directory_name)
                    if os.path.exists(post_dir):
                        shutil.rmtree(post_dir)
                        current_app.logger.info(f"Removed abandoned draft directory: {draft.directory_name}")
                else:
                    # Fallback for old structure (shouldn't happen with new posts)
                    current_app.logger.warning(f"Draft {draft.id} has no directory_name - skipping file cleanup")
                
                # Delete from database
                db.session.delete(draft)
                deleted_count += 1
                
            except Exception as e:
                current_app.logger.error(f"Error cleaning up draft {draft.id}: {str(e)}")
        
        if deleted_count > 0:
            db.session.commit()
            current_app.logger.info(f"Cleaned up {deleted_count} abandoned draft posts")
        
        return deleted_count
        
    except Exception as e:
        current_app.logger.error(f"Error in cleanup_abandoned_drafts: {str(e)}")
        db.session.rollback()
        return 0

@bp.route('/admin/write_post', methods=['GET', 'POST'])
@login_required
@role_required('Content Manager')
def admin_write_post():
    """
    Admin interface for writing posts
    """
    current_app.logger.info(f"admin_write_post called: method={request.method}, user={current_user.id}")
    try:
        from app.content.forms import WritePostForm
        current_app.logger.info("WritePostForm imported successfully")
        
        # Check if we're editing an existing draft
        draft_id = request.args.get('draft_id', type=int)
        # For POST requests, also check form data
        if not draft_id and request.method == 'POST':
            draft_id = request.form.get('draft_post_id', type=int)
        current_app.logger.info(f"Draft ID from request: {draft_id}")
        draft_post = None
        
        if draft_id:
            # Load existing draft
            draft_post = db.session.get(Post, draft_id)
            if not draft_post or draft_post.author_id != current_user.id or not draft_post.is_draft:
                flash('Draft not found or access denied.', 'error')
                return redirect(url_for('content.admin_write_post'))
        
        # Create form instance
        if draft_post:
            # Load draft content using new directory structure
            content = ""
            if draft_post.directory_name:
                markdown_path = get_post_file_path(draft_post.directory_name, draft_post.markdown_filename)
                if markdown_path and os.path.exists(markdown_path):
                    with open(markdown_path, 'r', encoding='utf-8') as f:
                        markdown_content = f.read()
                    from app.content.utils import parse_metadata_from_markdown
                    _, content = parse_metadata_from_markdown(markdown_content)
            
            form = WritePostForm(
                title=draft_post.title,
                summary=draft_post.summary,
                publish_on=draft_post.publish_on,
                expires_on=draft_post.expires_on,
                pin_until=draft_post.pin_until,
                tags=draft_post.tags,
                content=content
            )
        else:
            form = WritePostForm()
            
            # Create a new draft on GET request for new posts
            if request.method == 'GET':
                current_app.logger.info("Starting draft post creation for new post")
                try:
                    # Create draft post with fixed filenames
                    current_app.logger.info("Creating draft post object")
                    draft_post = Post(
                        title='Draft',
                        summary='Draft post',
                        publish_on=date.today(),
                        expires_on=date.today() + timedelta(days=current_app.config.get('POST_EXPIRATION_DAYS', 30)),
                        tags='',
                        markdown_filename='post.md',
                        html_filename='post.html',
                        author_id=current_user.id,
                        is_draft=True
                    )
                    current_app.logger.info("Draft post object created successfully")
                    
                    current_app.logger.info("Adding draft post to database session")
                    db.session.add(draft_post)
                    current_app.logger.info("Committing draft post to database")
                    db.session.commit()
                    current_app.logger.info(f"Draft post committed with ID: {draft_post.id}")
                    
                    # Create post directory now that we have an ID
                    current_app.logger.info("Creating post directory")
                    directory_name = create_post_directory(draft_post.id, 'Draft')
                    draft_post.directory_name = directory_name
                    db.session.commit()
                    current_app.logger.info(f"Created post directory: {directory_name}")
                    
                    # Create draft files using new directory structure
                    current_app.logger.info("Creating draft files")
                    markdown_path = get_post_file_path(draft_post.directory_name, 'post.md')
                    html_path = get_post_file_path(draft_post.directory_name, 'post.html')
                    current_app.logger.info(f"File paths: {markdown_path}, {html_path}")
                    
                    if markdown_path and html_path:
                        # Create empty draft files
                        current_app.logger.info("Writing markdown file")
                        with open(markdown_path, 'w', encoding='utf-8') as f:
                            f.write('---\ntitle: Draft\nsummary: Draft post\n---\n\n')
                        current_app.logger.info("Writing HTML file")
                        with open(html_path, 'w', encoding='utf-8') as f:
                            f.write('')
                        current_app.logger.info("Draft files created successfully")
                    else:
                        current_app.logger.warning("Could not get secure paths for draft files")
                    
                    current_app.logger.info(f"Draft post creation completed successfully with ID: {draft_post.id}")
                    
                except Exception as e:
                    current_app.logger.error(f"Error creating draft post: {str(e)}")
                    current_app.logger.error(f"Exception type: {type(e).__name__}")
                    import traceback
                    current_app.logger.error(f"Full traceback: {traceback.format_exc()}")
                    db.session.rollback()
                    current_app.logger.info("Database session rolled back due to error")
                    draft_post = None
            else:
                current_app.logger.info("GET request not detected, skipping draft creation")
                draft_post = None
        
        # Pass draft post ID to template for image uploads
        draft_post_id = draft_post.id if draft_post else None
        
        # Handle preview action BEFORE form validation (preview doesn't require validation)
        current_app.logger.info(f"Request method: {request.method}")
        if request.method == 'POST':
            action_value = request.form.get('action')
            current_app.logger.info(f"Action value from form: '{action_value}'")
            current_app.logger.info(f"All form keys: {list(request.form.keys())}")
            
        if request.method == 'POST' and request.form.get('action') == 'preview':
            current_app.logger.info("Preview action detected - bypassing form validation")
            
            # Get form data directly without validation
            title = request.form.get('title', '').strip()
            summary = request.form.get('summary', '').strip()
            content = request.form.get('content', '').strip()
            publish_on = form.publish_on.data or date.today()
            expires_on = form.expires_on.data or (date.today() + timedelta(days=30))
            pin_until = form.pin_until.data
            tags = request.form.get('tags', '').strip()
            
            # Handle image uploads for preview if any images are provided
            if draft_post and form.images.data:
                try:
                    uploaded_images = handle_image_uploads(form.images.data, draft_post)
                    if uploaded_images:
                        current_app.logger.info(f"Uploaded {len(uploaded_images)} images for preview")
                except Exception as e:
                    current_app.logger.error(f"Error uploading images for preview: {str(e)}")
            
            # Generate preview HTML without saving
            if content:
                import markdown2
                preview_html = markdown2.markdown(content, extras=['fenced-code-blocks', 'tables', 'header-ids', 'code-friendly'])
                preview_html = sanitize_html_content(preview_html)
            else:
                preview_html = '<p>No content to preview.</p>'
            
            # Use the existing draft post for preview to enable image serving
            if draft_post:
                preview_post = draft_post
                preview_post.title = title or 'Untitled'
                preview_post.summary = summary or 'No summary'
                preview_post.publish_on = publish_on
                preview_post.expires_on = expires_on
                preview_post.pin_until = pin_until
                preview_post.tags = tags
            else:
                # Create a preview post object (not saved to database)
                preview_post = Post(
                    title=title or 'Untitled',
                    summary=summary or 'No summary',
                    publish_on=publish_on,
                    expires_on=expires_on,
                    pin_until=pin_until,
                    tags=tags,
                    author_id=current_user.id,
                    is_draft=True
                )
                preview_post.id = 'preview'  # Set a dummy ID for preview if no draft exists
            
            return render_template('view_post.html', post=preview_post, content=preview_html, is_preview=True)
        
        if form.validate_on_submit():
            current_app.logger.info("Form validation successful")
            
            # Check which action was submitted
            action = request.form.get('action', 'publish')
            current_app.logger.info(f"Form action: {action}")
            
            # Handle image uploads first if there are any
            uploaded_images = []
            current_app.logger.info(f"Image data present: {bool(form.images.data)}, Draft post: {bool(draft_post)}")
            
            # For POST requests, we need to get the draft post ID from a hidden field or create a new post first
            post_for_images = draft_post
            if not post_for_images and form.images.data:
                current_app.logger.info("No draft post available for images, will handle after post creation")
            elif form.images.data and post_for_images:
                current_app.logger.info(f"Processing image uploads for post {post_for_images.id}")
                uploaded_images = handle_image_uploads(form.images.data, post_for_images)
                current_app.logger.info(f"Image upload completed: {len(uploaded_images)} images processed")
            
            # Get form data
            title = form.title.data.strip()
            summary = form.summary.data.strip()
            content = request.form.get('content', '').strip()  # Content field might not be in the form
            tags = form.tags.data.strip() if form.tags.data else ''
            publish_on = form.publish_on.data
            expires_on = form.expires_on.data
            pin_until = form.pin_until.data
            
            # Validate required fields for publish action (drafts can have empty content)
            if action == 'publish' and (not title or not summary or not content):
                flash('Title, summary, and content are required for publishing.', 'error')
                return render_template('admin_write_post.html', form=form, draft_post_id=draft_post_id)
            elif action == 'save_draft' and not title:
                flash('Title is required for saving draft.', 'error')
                return render_template('admin_write_post.html', form=form, draft_post_id=draft_post_id)
            
            # Determine if this should be a draft or published post
            is_draft = (action == 'save_draft')
            
            if draft_post:
                # Update existing draft or publish it
                post = draft_post
                old_title = post.title  # Store old title for directory renaming check
                post.title = title
                post.summary = summary
                post.publish_on = publish_on
                post.expires_on = expires_on
                post.pin_until = pin_until
                post.tags = tags
                post.is_draft = is_draft
                
                markdown_filename = post.markdown_filename
                html_filename = post.html_filename
            else:
                # Create post in database first (we need the ID for directory creation)
                post = Post(
                    title=title,
                    summary=summary,
                    publish_on=publish_on,
                    expires_on=expires_on,
                    pin_until=pin_until,
                    tags=tags,
                    markdown_filename='post.md',  # Fixed filename in new structure
                    html_filename='post.html',    # Fixed filename in new structure
                    author_id=current_user.id,
                    is_draft=is_draft
                )
            
            try:
                if not draft_post:
                    db.session.add(post)
                    db.session.commit()
                    
                    # Create post directory now that we have an ID
                    directory_name = create_post_directory(post.id, title or 'draft')
                    post.directory_name = directory_name
                    db.session.commit()  # Save directory name
                    
                    current_app.logger.info(f"Created post directory: {directory_name}")
                else:
                    # For existing drafts, check if directory needs to be renamed due to title change
                    if post.directory_name and old_title != title:
                        old_directory_name = post.directory_name
                        new_directory = rename_post_directory(post.directory_name, title)
                        if new_directory and new_directory != post.directory_name:
                            post.directory_name = new_directory
                            current_app.logger.info(f"Renamed post directory from {old_directory_name} to {new_directory}")
                        else:
                            current_app.logger.info(f"Directory rename not needed or failed for post {post.id}")
                    
                    db.session.commit()
                
                # Handle image uploads after post is created/updated
                if form.images.data and not uploaded_images:
                    current_app.logger.info(f"Processing image uploads for post {post.id} after creation")
                    uploaded_images = handle_image_uploads(form.images.data, post)
                    current_app.logger.info(f"Post-creation image upload completed: {len(uploaded_images)} images processed")
                
                # Get secure file paths using new directory structure
                markdown_path = get_post_file_path(post.directory_name, 'post.md')
                html_path = get_post_file_path(post.directory_name, 'post.html')
                
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
                
                # Audit log the post creation/update
                if draft_post:
                    if is_draft:
                        audit_log_update('Post', post.id, f'Updated draft: {title}')
                        flash('Draft saved successfully!', 'success')
                    else:
                        audit_log_update('Post', post.id, f'Published post: {title}')
                        flash('Post published successfully!', 'success')
                else:
                    if is_draft:
                        audit_log_create('Post', post.id, f'Created draft: {title}')
                        flash('Draft saved successfully!', 'success')
                    else:
                        audit_log_create('Post', post.id, f'Created post: {title}',
                                       {'publish_on': publish_on.isoformat(), 'expires_on': expires_on.isoformat()})
                        flash('Post published successfully!', 'success')
                
                return redirect(url_for('content.admin_manage_posts'))
                
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error creating post: {str(e)}")
                flash('An error occurred while creating the post.', 'error')
                return render_template('admin_write_post.html', form=form, draft_post_id=draft_post_id)
        
        # GET request - render form
        current_app.logger.info(f"Rendering template with draft_post_id: {draft_post_id}")
        return render_template('admin_write_post.html', form=form, draft_post_id=draft_post_id)
        
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
        # Show all posts (including drafts) for content managers
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
                    
                    # Move files to secure archive storage using new directory structure
                    if post.directory_name:
                        markdown_path = get_post_file_path(post.directory_name, post.markdown_filename)
                        html_path = get_post_file_path(post.directory_name, post.html_filename)
                    else:
                        markdown_path = None
                        html_path = None
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

        # Load the post content from secure storage using new directory structure
        if post.directory_name:
            markdown_path = get_post_file_path(post.directory_name, post.markdown_filename)
            html_path = get_post_file_path(post.directory_name, post.html_filename)
        else:
            # Fallback for old posts without directory_name (shouldn't happen since we deleted all)
            current_app.logger.warning(f"Post {post.id} has no directory_name - this should not happen with new structure")
            markdown_path = None
            html_path = None
        
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

        # Handle preview action BEFORE form validation (preview doesn't require validation)
        if request.method == 'POST' and request.form.get('action') == 'preview':
            current_app.logger.info("Preview action detected in edit_post - bypassing form validation")
            
            # Get form data directly without validation
            title = request.form.get('title', '').strip()
            summary = request.form.get('summary', '').strip()
            content = request.form.get('content', '').strip()
            publish_on = post.publish_on  # Use existing post dates for preview
            expires_on = post.expires_on
            pin_until = post.pin_until
            tags = request.form.get('tags', '').strip()
            
            # Generate preview HTML without saving
            if content:
                import markdown2
                preview_html = markdown2.markdown(content, extras=['fenced-code-blocks', 'tables', 'header-ids', 'code-friendly'])
                preview_html = sanitize_html_content(preview_html)
            else:
                preview_html = '<p>No content to preview.</p>'
            
            # Create a preview post object (not saved to database) 
            # Use the actual post's ID so image serving works correctly
            preview_post = Post(
                title=title or 'Untitled',
                summary=summary or 'No summary',
                publish_on=publish_on,
                expires_on=expires_on,
                pin_until=pin_until,
                tags=tags,
                author_id=current_user.id,
                is_draft=True
            )
            preview_post.id = post.id  # Use actual post ID for image serving
            preview_post.directory_name = post.directory_name  # Use actual directory for images
            
            return render_template('view_post.html', post=preview_post, content=preview_html, is_preview=True)

        if form.validate_on_submit():
            # Check which action was submitted
            action = request.form.get('action', 'publish')
            current_app.logger.info(f"Edit post form action: {action}")
            
            # Validate required fields for publish action (drafts can have empty content)
            if action == 'publish' and (not form.title.data or not form.summary.data or not form.content.data):
                flash('Title, summary, and content are required for publishing.', 'error')
                return render_template('admin_write_post.html', form=form, post=post)
            elif action == 'save_draft' and not form.title.data:
                flash('Title is required for saving draft.', 'error')
                return render_template('admin_write_post.html', form=form, post=post)
            
            # Determine if this should be a draft or published post
            is_draft = (action == 'save_draft')
            
            # Capture changes for audit log
            changes = get_model_changes(post, {
                'title': form.title.data,
                'summary': form.summary.data,
                'publish_on': form.publish_on.data,
                'expires_on': form.expires_on.data,
                'pin_until': form.pin_until.data,
                'tags': form.tags.data,
                'is_draft': is_draft
            })
            
            # Update the post metadata
            old_title = post.title  # Store old title for directory renaming check
            post.title = form.title.data
            post.summary = form.summary.data
            post.publish_on = form.publish_on.data
            post.expires_on = form.expires_on.data
            post.pin_until = form.pin_until.data
            post.tags = form.tags.data
            post.is_draft = is_draft
            
            # Check if directory needs to be renamed due to title change
            if post.directory_name and old_title != form.title.data:
                old_directory_name = post.directory_name
                new_directory = rename_post_directory(post.directory_name, form.title.data)
                if new_directory and new_directory != post.directory_name:
                    post.directory_name = new_directory
                    current_app.logger.info(f"Renamed post directory from {old_directory_name} to {new_directory}")
                else:
                    current_app.logger.info(f"Directory rename not needed or failed for post {post.id}")

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
            
            # Audit log the post update with action-specific messaging
            if is_draft:
                audit_log_update('Post', post.id, f'Updated draft: {post.title}', changes)
                flash('Draft updated successfully!', 'success')
            else:
                audit_log_update('Post', post.id, f'Updated and published post: {post.title}', changes)
                flash('Post updated and published successfully!', 'success')
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
        
        # Archive the post files before deletion using new directory structure
        if post.directory_name:
            markdown_path = get_post_file_path(post.directory_name, post.markdown_filename)
            html_path = get_post_file_path(post.directory_name, post.html_filename)
        else:
            markdown_path = None
            html_path = None
        
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


# Image serving routes

@bp.route('/image/<int:post_id>/<filename>')
@login_required
def serve_post_image(post_id, filename):
    """
    Serve post images with authentication protection
    """
    try:
        # Verify post exists and user can access it
        post = db.session.get(Post, post_id)
        if not post:
            current_app.logger.warning(f"Image request for non-existent post: {post_id}")
            abort(404)
        
        # Check if post is published (non-draft) or user is the author
        if post.is_draft and post.author_id != current_user.id:
            current_app.logger.warning(f"Unauthorized access to draft post image: user {current_user.id}, post {post_id}")
            abort(403)
        
        # For published posts, check date restrictions
        if not post.is_draft:
            today = date.today()
            if post.publish_on > today or post.expires_on < today:
                current_app.logger.warning(f"Access to expired/unpublished post image: post {post_id}")
                abort(404)
        
        # Get secure image path using new directory structure
        if not post.directory_name:
            current_app.logger.error(f"Post {post_id} has no directory_name")
            abort(404)
        
        image_path = get_post_image_path(post.directory_name, filename)
        if not image_path:
            current_app.logger.error(f"Could not get secure image path for {filename} in {post.directory_name}")
            abort(403)
        
        # Check if file exists
        if not os.path.exists(image_path):
            current_app.logger.warning(f"Image file not found: {image_path}")
            abort(404)
        
        # Serve the file
        from flask import send_file
        return send_file(image_path)
        
    except Exception as e:
        current_app.logger.error(f"Error serving image {filename} for post {post_id}: {str(e)}")
        abort(500)


# Public content viewing routes

@bp.route("/post/<int:post_id>")
@login_required
def view_post(post_id):
    """
    Display a single post with full content
    """
    try:
        from flask import abort
        
        today = date.today()
        
        # Get post by ID and validate publish/expire dates
        post = db.session.scalar(
            sa.select(Post).where(
                Post.id == post_id,
                Post.is_draft == False,     # Only show published posts
                Post.publish_on <= today,   # Only show posts that should be published
                Post.expires_on >= today    # Only show posts that haven't expired
            )
        )
        if not post:
            current_app.logger.error(f"Post not found or not available with ID: {post_id}")
            abort(404)
        
        current_app.logger.info(f"Found post: {post.title}, HTML file: {post.html_filename}")
        
        # Get the HTML content from secure storage using new directory structure
        if post.directory_name:
            html_path = get_post_file_path(post.directory_name, post.html_filename)
        else:
            html_path = None
        
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