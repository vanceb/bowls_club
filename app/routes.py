from flask import render_template, flash, redirect, url_for, request, abort, jsonify, current_app
from app import app, db

from app.forms import LoginForm, MemberForm, EditMemberForm, RequestResetForm, ResetPasswordForm, WritePostForm, BookingForm
from flask_login import current_user, login_user, logout_user, login_required
from urllib.parse import urlsplit
import sqlalchemy as sa
from werkzeug.security import generate_password_hash
from app.models import Member, Role, Post, Booking
from functools import wraps
from app.utils import generate_reset_token, verify_reset_token, send_reset_email, sanitize_filename
from datetime import datetime, timedelta, date
import os
from markdown2 import markdown
from flask_paginate import Pagination, get_page_parameter
from app.utils import parse_metadata_from_markdown
import shutil


# Decorator to restrict access to admin-only routes
def admin_required(f):
    """
    Decorator to restrict access to admin-only routes.
    - Checks if the current user is authenticated and has admin privileges.
    - Aborts with a 403 status if the user is not authorized.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function


@app.route("/")
@app.route("/index")
@login_required
def index():
    """
    Route: Home page
    - Displays pinned and non-pinned posts with pagination.
    - Requires login.
    """
    today = date.today()

    # Fetch pinned posts
    pinned_posts_query = sa.select(Post).where(
        Post.pin_until >= today  # A post is pinned if pin_until is in the future
    ).order_by(Post.publish_on.desc())
    pinned_posts = db.session.scalars(pinned_posts_query).all()

    # Fetch non-pinned posts
    non_pinned_posts_query = sa.select(Post).where(
        sa.or_(Post.pin_until < today, Post.pin_until == None),  # Not pinned
        Post.publish_on <= today,
        Post.expires_on >= today
    ).order_by(Post.publish_on.desc())
    non_pinned_posts = db.session.scalars(non_pinned_posts_query).all()

    # Pagination for non-pinned posts
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = current_app.config.get('POSTS_PER_PAGE', 5)  # Use the config value
    start = (page - 1) * per_page
    end = start + per_page
    paginated_non_pinned_posts = non_pinned_posts[start:end]

    pagination = Pagination(page=page, total=len(non_pinned_posts), per_page=per_page, css_framework='bulma')

    return render_template(
        'index.html',
        title='Home',
        pinned_posts=pinned_posts,
        non_pinned_posts=paginated_non_pinned_posts,
        pagination=pagination,
        current_page=page,
        menu_items=app.config['MENU_ITEMS'],
        admin_menu_items=app.config['ADMIN_MENU_ITEMS']
    )


@app.route("/post/<int:post_id>")
@login_required
def view_post(post_id):
    """
    Route: View Post
    - Displays the content of a specific post.
    - Requires login.
    """
    post = db.session.get(Post, post_id)
    if not post:
        abort(404)

    # Load the HTML content from the static/posts directory
    post_path = os.path.join(current_app.static_folder, 'posts', post.html_filename)
    if not os.path.exists(post_path):
        abort(404)

    with open(post_path, 'r') as file:
        post_content = file.read()

    return render_template(
        'view_post.html',
        post=post,
        post_content=post_content,
        menu_items=app.config['MENU_ITEMS'],
        admin_menu_items=app.config['ADMIN_MENU_ITEMS']
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Route: Login page
    - Handles user login with username and password.
    - Redirects authenticated users to the home page.
    """
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(Member).where(Member.username == form.username.data)
        )
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        if user.status in ['Pending', 'Suspended']:  # Restrict login
            flash('Your account is not active. Please contact the administrator.')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)

    return render_template('login.html', title='Sign In', form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/add_member', methods=['GET', 'POST'])
def add_member():
    form = MemberForm()
    if form.validate_on_submit():
        # Create a new Member instance
        new_member = Member(
            username=form.username.data,
            firstname=form.firstname.data,
            lastname=form.lastname.data,
            email=form.email.data,
            phone=form.phone.data,
            password_hash=generate_password_hash(form.password.data),
            status="Pending"  # Set default status
        )
        # Add to the database
        db.session.add(new_member)
        db.session.commit()
        flash(f'Joining application submitted for {form.firstname.data} {form.lastname.data}', 'success')
        return redirect(url_for('login'))  # Redirect to the homepage or another page
    if form.errors:
        flash(f'There are errors in your application. Please review your application and try again.', 'danger')
    return render_template('add_member.html', form=form, menu_items=app.config['MENU_ITEMS'], admin_menu_items=app.config['ADMIN_MENU_ITEMS'])


@app.route('/members')
@login_required
def members():
    """
    Route: Members page
    - Displays a list of all members sorted by their first name.
    - Requires login.
    """
    members = db.session.scalars(sa.select(Member).order_by(Member.firstname)).all()
    return render_template('members.html', members=members, menu_items=app.config['MENU_ITEMS'], admin_menu_items=app.config['ADMIN_MENU_ITEMS'])


@app.route('/search_members', methods=['GET'])
@login_required
def search_members():
    """
    Route: Search Members
    - Allows searching for members by first name, last name, or email.
    - Returns a JSON response with member details, including roles.
    - Requires login.
    """
    query = request.args.get('q', '').strip()
    members = Member.query.filter(
        (Member.firstname.ilike(f'%{query}%')) |
        (Member.lastname.ilike(f'%{query}%')) |
        (Member.email.ilike(f'%{query}%'))
    ).all()

    return jsonify({
        'members': [
            {
                'id': member.id,
                'firstname': member.firstname,
                'lastname': member.lastname,
                'username': member.username,
                'email': member.email,
                'phone': member.phone,
                'gender': member.gender,
                'status': member.status,
                'roles': [{'id': role.id, 'name': role.name} for role in member.roles]
            }
            for member in members
        ]
    })



@app.route('/admin/manage_members', methods=['GET'])
@admin_required
def manage_members():
    """
    Route: Manage Members
    - Displays a list of all members for administrative management.
    - Requires admin privileges.
    """
    members = db.session.scalars(sa.select(Member).order_by(Member.firstname)).all()
    return render_template(
        'manage_members.html',
        title='Manage Members',
        members=members,
        menu_items=app.config['MENU_ITEMS'],
        admin_menu_items=app.config['ADMIN_MENU_ITEMS']
    )


@app.route('/admin/edit_member/<int:member_id>', methods=['GET', 'POST'])
@admin_required
def edit_member(member_id):
    """
    Route: Edit Member
    - Allows admins to edit or delete a member's details.
    - Fetches the member by ID and pre-populates the form with their details.
    - Updates member details or deletes the member based on the form submission.
    - Requires admin privileges.
    """
    member = db.session.get(Member, member_id)
    if not member:
        abort(404)

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
            member.username = form.username.data
            member.firstname = form.firstname.data
            member.lastname = form.lastname.data
            member.email = form.email.data
            member.phone = form.phone.data
            member.is_admin = form.is_admin.data
            member.gender = form.gender.data
            member.status = form.status.data

            selected_role_ids = form.roles.data
            selected_roles = db.session.scalars(sa.select(Role).where(Role.id.in_(selected_role_ids))).all()
            member.roles = selected_roles

            db.session.commit()
            flash('Member updated successfully', 'success')
            return redirect(url_for('manage_members'))
        elif form.submit_delete.data:
            # Delete the member
            db.session.delete(member)
            db.session.commit()
            flash('Member deleted successfully', 'success')
            return redirect(url_for('manage_members'))

    return render_template(
        'edit_member.html',
        form=form,
        member=member,
        roles=roles,
        menu_items=app.config['MENU_ITEMS'],
        admin_menu_items=app.config['ADMIN_MENU_ITEMS']
    )


@app.route('/admin/manage_roles', methods=['GET', 'POST'])
@admin_required
def manage_roles():
    """
    Route: Manage Roles
    - Allows admins to create, rename, or delete roles.
    - Displays a list of all roles.
    - Requires admin privileges.
    """
    roles = db.session.scalars(sa.select(Role).order_by(Role.name)).all()

    if request.method == 'POST':
        action = request.form.get('action')
        role_id = request.form.get('role_id')
        role_name = request.form.get('role_name', '').strip()

        if action == 'create' and role_name:
            # Create a new role
            if db.session.scalar(sa.select(Role).where(Role.name == role_name)):
                flash('Role already exists.', 'danger')
            else:
                new_role = Role(name=role_name)
                db.session.add(new_role)
                db.session.commit()
                flash('Role created successfully.', 'success')

        elif action == 'rename' and role_id and role_name:
            # Rename an existing role
            role = db.session.get(Role, int(role_id))
            if role:
                if db.session.scalar(sa.select(Role).where(Role.name == role_name)):
                    flash('A role with this name already exists.', 'danger')
                else:
                    role.name = role_name
                    db.session.commit()
                    flash('Role renamed successfully.', 'success')
            else:
                flash('Role not found.', 'danger')

        elif action == 'delete' and role_id:
            # Delete an existing role
            role = db.session.get(Role, int(role_id))
            if role:
                db.session.delete(role)
                db.session.commit()
                flash('Role deleted successfully.', 'success')
            else:
                flash('Role not found.', 'danger')

        return redirect(url_for('manage_roles'))

    return render_template(
        'manage_roles.html',
        roles=roles,
        menu_items=app.config['MENU_ITEMS'],
        admin_menu_items=app.config['ADMIN_MENU_ITEMS']
    )


@app.route('/reset_password', methods=['GET', 'POST'])
def pw_reset_request():
    """
    Route: Password Reset Request
    - Allows users to request a password reset by providing their email.
    - Sends a reset email with a token if the email is registered.
    """
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(Member).where(Member.email == form.email.data))
        if user:
            token = generate_reset_token(user.email)
            reset_url = url_for('pw_reset', token=token, _external=True)
            send_reset_email(user.email, reset_url)

        flash('If that email address is registered, you will receive an email with instructions to reset your password.', 'info')
        return redirect(url_for('login'))
    return render_template('pw_reset_request.html', form=form)


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def pw_reset(token):
    """
    Route: Password Reset
    - Allows users to reset their password using a valid token.
    - Verifies the token and updates the user's password.
    """
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    email = verify_reset_token(token)
    if not email:
        flash('That is an invalid or expired token.', 'danger')
        return redirect(url_for('pw_reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(Member).where(Member.email == email))
        if user:
            user.set_password(form.password.data)
            db.session.commit()
            flash('Your password has been updated!', 'success')
            return redirect(url_for('login'))
    return render_template('pw_reset.html', form=form)


@app.route('/admin/write_post', methods=['GET', 'POST'])
@admin_required
def write_post():
    """
    Route: Write Post
    - Allows admins to create a new post.
    """
    form = WritePostForm()

    # Set default values for the form fields
    if request.method == 'GET':
        form.publish_on.data = date.today()
        form.expires_on.data = date.today() + timedelta(days=current_app.config.get('POST_EXPIRATION_DAYS', 30))

    if form.validate_on_submit():
        # Generate filenames
        timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        safe_title = sanitize_filename(form.title.data)[:31]
        markdown_filename = f"{timestamp}_{safe_title}.md"
        html_filename = f"{timestamp}_{safe_title}.html"

        # Save metadata to the database
        post = Post(
            title=form.title.data,
            summary=form.summary.data,
            publish_on=form.publish_on.data,
            expires_on=form.expires_on.data,
            pin_until=form.pin_until.data,
            tags=form.tags.data,
            author_id=current_user.id,
            markdown_filename=markdown_filename,
            html_filename=html_filename
        )
        db.session.add(post)
        db.session.commit()

        # Save content as a Markdown file
        post_dir = os.path.join(current_app.static_folder, 'posts')
        os.makedirs(post_dir, exist_ok=True)
        markdown_path = os.path.join(post_dir, markdown_filename)
        html_path = os.path.join(post_dir, html_filename)

        metadata = f"""---
title: {post.title}
summary: {post.summary}
publish_on: {post.publish_on}
expires_on: {post.expires_on}
pin_until: {post.pin_until}
tags: {post.tags}
author: {current_user.username}
---
"""
        with open(markdown_path, 'w') as md_file:
            md_file.write(metadata + '\n' + form.content.data)

        # Convert Markdown to HTML and save
        html_content = markdown(form.content.data, extras=["tables"])
        with open(html_path, 'w') as html_file:
            html_file.write(html_content)

        flash('Post created successfully!', 'success')
        return redirect(url_for('index'))

    return render_template('write_post.html', form=form, menu_items=app.config['MENU_ITEMS'], admin_menu_items=app.config['ADMIN_MENU_ITEMS'])


@app.route('/manage_posts', methods=['GET', 'POST'])
@login_required
def manage_posts():
    """
    Route: Manage Posts
    - Displays a list of posts with checkboxes and metadata.
    - Handles deletion of selected posts.
    """
    today = date.today()
    posts_query = sa.select(Post).order_by(Post.expires_on.asc())
    posts = db.session.scalars(posts_query).all()

    if request.method == 'POST':
        # Handle deletion of selected posts
        post_ids = request.form.getlist('post_ids')
        for post_id in post_ids:
            post = db.session.get(Post, post_id)
            if post:
                # Move markdown file to archive folder
                markdown_path = os.path.join(current_app.static_folder, 'posts', post.markdown_filename)
                html_path = os.path.join(current_app.static_folder, 'posts', post.html_filename)
                archive_markdown_path = os.path.join(current_app.static_folder, 'archive', post.markdown_filename)
                archive_html_path = os.path.join(current_app.static_folder, 'archive', post.html_filename)

                # Ensure the archive directory exists
                os.makedirs(os.path.dirname(archive_markdown_path), exist_ok=True)

                # Move Markdown file if it exists
                if os.path.exists(markdown_path):
                    shutil.move(markdown_path, archive_markdown_path)

                # Move HTML file if it exists
                if os.path.exists(html_path):
                    shutil.move(html_path, archive_html_path)

                # Delete post from database
                db.session.delete(post)
        db.session.commit()
        flash(f"{len(post_ids)} post(s) deleted successfully!", "success")
        return redirect(url_for('manage_posts'))

    return render_template(
        'manage_posts.html',
        title='Manage Posts',
        posts=posts,
        today=today,
        menu_items=app.config['MENU_ITEMS'],
        admin_menu_items=app.config['ADMIN_MENU_ITEMS'],
    )


@app.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    """
    Route: Edit Post
    - Loads post metadata and content for editing.
    - Reuses the write_post.html template.
    """
    post = db.session.get(Post, post_id)
    if not post:
        abort(404)

    # Load the post content from the markdown file
    markdown_path = os.path.join(current_app.static_folder, 'posts', post.markdown_filename)
    html_path = os.path.join(current_app.static_folder, 'posts', post.html_filename)
    if not os.path.exists(markdown_path):
        abort(404)

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
        # Update the post metadata
        post.title = form.title.data
        post.summary = form.summary.data
        post.publish_on = form.publish_on.data
        post.expires_on = form.expires_on.data
        post.pin_until = form.pin_until.data
        post.tags = form.tags.data

        # Update the markdown file
        updated_markdown = f"""---
title: {form.title.data}
summary: {form.summary.data}
publish_on: {form.publish_on.data}
expires_on: {form.expires_on.data}
pin_until: {form.pin_until.data}
tags: {form.tags.data}
author: {post.author_id}
---

{form.content.data}
"""
        with open(markdown_path, 'w') as file:
            file.write(updated_markdown)

        # Convert the updated Markdown to HTML and overwrite the HTML file
        updated_html = markdown(form.content.data, extras=["tables"])
        with open(html_path, 'w') as file:
            file.write(updated_html)

        # Save changes to the database
        db.session.commit()
        flash("Post updated successfully!", "success")
        return redirect(url_for('manage_posts'))

    return render_template(
        'write_post.html',
        title='Edit Post',
        form=form,
        menu_items=app.config['MENU_ITEMS'],
        admin_menu_items=app.config['ADMIN_MENU_ITEMS'],
    )


@app.route('/admin/create_booking', methods=['GET', 'POST'])
@admin_required
def create_booking():
    """
    Route: Create Booking
    - Allows users to create a new booking.
    - Requires login.
    """
    form = BookingForm()
    if form.validate_on_submit():
        booking = Booking(
            booking_date=form.booking_date.data,
            session=form.session.data,
            rink=form.rink.data,
            priority=form.priority.data
        )
        db.session.add(booking)
        db.session.commit()
        flash('Booking created successfully!', 'success')
        return redirect(url_for('create_booking'))
    return render_template('booking_form.html', form=form, menu_items=app.config['MENU_ITEMS'], admin_menu_items=app.config['ADMIN_MENU_ITEMS'])


@app.route('/bookings')
@login_required
def bookings():
    """
    Route: Bookings Table
    - Renders the bookings table page.
    """
    return render_template('bookings_table.html', title="Bookings", today=date.today().isoformat(), menu_items=app.config['MENU_ITEMS'], admin_menu_items=app.config['ADMIN_MENU_ITEMS'])

@app.route('/get_bookings/<string:selected_date>')
@login_required
def get_bookings(selected_date):
    """
    Route: Get Bookings
    - Returns bookings for a specific date in JSON format.
    """
    # Validate the date format
    try:
        selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400

    # Query bookings for the selected date
    bookings_query = sa.select(Booking).where(Booking.booking_date == selected_date)
    bookings = db.session.scalars(bookings_query).all()

    # Prepare data for the table
    bookings_data = [{'rink': booking.rink, 'session': booking.session} for booking in bookings]
    rinks = current_app.config['RINKS']
    sessions = current_app.config['DAILY_SESSIONS']

    return jsonify({'bookings': bookings_data, 'rinks': rinks, 'sessions': sessions, 'menu_items': app.config['MENU_ITEMS'], 'admin_menu_items': app.config['ADMIN_MENU_ITEMS']})
