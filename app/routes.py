# Standard library imports
import os
import shutil
from datetime import datetime, timedelta, date
from functools import wraps
from urllib.parse import urlsplit

# Third-party imports
import sqlalchemy as sa
import yaml
from flask import render_template, flash, redirect, url_for, request, abort, jsonify, current_app
from flask_login import current_user, login_user, logout_user, login_required
from flask_paginate import Pagination, get_page_parameter
from markdown2 import markdown
from werkzeug.security import generate_password_hash

# Local application imports
from app import app, db, limiter
from app.forms import (
    LoginForm, MemberForm, EditMemberForm, RequestResetForm, 
    ResetPasswordForm, WritePostForm, BookingForm, EventForm, 
    EventSelectionForm
)
from app.models import Member, Role, Post, Booking, Event
from app.utils import (
    generate_reset_token, verify_reset_token, send_reset_email, 
    sanitize_filename, parse_metadata_from_markdown, sanitize_html_content,
    get_secure_post_path, get_secure_archive_path, generate_secure_filename
)


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


# Role-based decorators for fine-grained access control
def role_required(*required_roles):
    """
    Decorator to restrict access based on user roles.
    - Checks if the current user is authenticated and has one of the required roles.
    - Admin users bypass role checks.
    - Aborts with a 403 status if the user is not authorized.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(403)  # Forbidden
            
            # Admin users bypass role checks
            if current_user.is_admin:
                return f(*args, **kwargs)
            
            # Check if user has any of the required roles
            user_role_names = [role.name for role in current_user.roles]
            if any(role in user_role_names for role in required_roles):
                return f(*args, **kwargs)
            
            abort(403)  # Forbidden
        return decorated_function
    return decorator


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

    # Load the HTML content from secure storage
    post_path = get_secure_post_path(post.html_filename)
    if not post_path or not os.path.exists(post_path):
        abort(404)

    with open(post_path, 'r') as file:
        post_content = file.read()

    # Sanitize the HTML content to prevent XSS
    safe_post_content = sanitize_html_content(post_content)

    return render_template(
        'view_post.html',
        post=post,
        post_content=safe_post_content,
        menu_items=app.config['MENU_ITEMS'],
        admin_menu_items=app.config['ADMIN_MENU_ITEMS']
    )


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
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
    """
    Route: Logout
    - Logs out the current user and redirects to home page.
    - Clears the user session.
    """
    logout_user()
    return redirect(url_for('index'))


@app.route('/add_member', methods=['GET', 'POST'])
@limiter.limit("3 per minute")
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
    - Allows searching for members by username, first name, last name, or email.
    - Returns a JSON response with member details, including roles.
    - Requires login.
    """
    query = request.args.get('q', '').strip()
    members = db.session.scalars(sa.select(Member).where(
        (Member.username.ilike(f'%{query}%')) |
        (Member.firstname.ilike(f'%{query}%')) |
        (Member.lastname.ilike(f'%{query}%')) |
        (Member.email.ilike(f'%{query}%'))
    )).all()

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
@role_required('User Manager')
def manage_members():
    """
    Route: Manage Members
    - Displays a list of all members for administrative management.
    - Requires User Manager role or admin privileges.
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
@role_required('User Manager')
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
    - Requires User Manager role or admin privileges.
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
@limiter.limit("3 per minute")
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
@role_required('Content Manager')
def write_post():
    """
    Route: Write Post
    - Allows Content Managers to create a new post.
    """
    form = WritePostForm()

    # Set default values for the form fields
    if request.method == 'GET':
        form.publish_on.data = date.today()
        form.expires_on.data = date.today() + timedelta(days=current_app.config.get('POST_EXPIRATION_DAYS', 30))

    if form.validate_on_submit():
        # Generate secure filenames using UUID
        markdown_filename = generate_secure_filename(form.title.data, '.md')
        html_filename = generate_secure_filename(form.title.data, '.html')

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

        # Save content to secure storage
        post_dir = current_app.config['POSTS_STORAGE_PATH']
        os.makedirs(post_dir, exist_ok=True)
        markdown_path = get_secure_post_path(markdown_filename)
        html_path = get_secure_post_path(html_filename)
        
        # Validate secure paths
        if not markdown_path or not html_path:
            abort(400)  # Bad request for invalid filenames

        # Create metadata dictionary and serialize to YAML
        metadata_dict = {
            'title': post.title,
            'summary': post.summary,
            'publish_on': post.publish_on,
            'expires_on': post.expires_on,
            'pin_until': post.pin_until,
            'tags': post.tags,
            'author': current_user.username
        }
        metadata = "---\n" + yaml.dump(metadata_dict, default_flow_style=False) + "---\n"
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
@role_required('Content Manager')
def manage_posts():
    """
    Route: Manage Posts
    - Displays a list of posts with checkboxes and metadata.
    - Handles deletion of selected posts.
    """
    today = date.today()
    posts_query = sa.select(Post).order_by(Post.created_at.desc())
    posts = db.session.scalars(posts_query).all()

    if request.method == 'POST':
        # Handle deletion of selected posts
        post_ids = request.form.getlist('post_ids')
        for post_id in post_ids:
            post = db.session.get(Post, post_id)
            if post:
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

    # Load the post content from secure storage
    markdown_path = get_secure_post_path(post.markdown_filename)
    html_path = get_secure_post_path(post.html_filename)
    if not markdown_path or not html_path or not os.path.exists(markdown_path):
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
        # Create metadata dictionary and serialize to YAML
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
        flash("Post updated successfully!", "success")
        return redirect(url_for('manage_posts'))

    return render_template(
        'write_post.html',
        title='Edit Post',
        form=form,
        menu_items=app.config['MENU_ITEMS'],
        admin_menu_items=app.config['ADMIN_MENU_ITEMS'],
    )



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
    - Returns booking counts per session for a specific date in JSON format.
    """
    # Validate the date format
    try:
        selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400

    # Query booking counts grouped by session for the selected date
    booking_counts_query = sa.select(
        Booking.session,
        sa.func.sum(Booking.rink_count).label('total_rinks')
    ).where(
        Booking.booking_date == selected_date
    ).group_by(Booking.session)
    
    booking_counts = db.session.execute(booking_counts_query).all()

    # Prepare data for the table - convert to dict with session as key
    bookings_data = {}
    for session, total_rinks in booking_counts:
        bookings_data[session] = total_rinks

    rinks = current_app.config['RINKS']
    sessions = current_app.config['DAILY_SESSIONS']

    return jsonify({
        'bookings': bookings_data, 
        'rinks': rinks, 
        'sessions': sessions, 
        'menu_items': app.config['MENU_ITEMS'], 
        'admin_menu_items': app.config['ADMIN_MENU_ITEMS']
    })


@app.route('/get_bookings_range/<string:start_date>/<string:end_date>')
@login_required
def get_bookings_range(start_date, end_date):
    """
    Route: Get Bookings Range
    - Returns booking counts per session for a date range in JSON format.
    - Used for the new table layout with dates as rows and sessions as columns.
    """
    # Validate the date formats
    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400

    # Query booking counts grouped by date and session for the date range
    booking_counts_query = sa.select(
        Booking.booking_date,
        Booking.session,
        sa.func.sum(Booking.rink_count).label('total_rinks')
    ).where(
        Booking.booking_date >= start_date,
        Booking.booking_date <= end_date
    ).group_by(Booking.booking_date, Booking.session)
    
    booking_counts = db.session.execute(booking_counts_query).all()

    # Prepare data structure: {date: {session: count}}
    bookings_data = {}
    for booking_date, session, total_rinks in booking_counts:
        date_str = booking_date.isoformat()
        if date_str not in bookings_data:
            bookings_data[date_str] = {}
        bookings_data[date_str][session] = total_rinks

    rinks = current_app.config['RINKS']
    sessions = current_app.config['DAILY_SESSIONS']

    return jsonify({
        'bookings': bookings_data, 
        'rinks': rinks, 
        'sessions': sessions
    })


@app.route('/get_availability/<string:selected_date>/<int:session_id>')
@login_required
def get_availability(selected_date, session_id):
    """
    Route: Get Availability
    - Returns available rinks for a specific date and session.
    - Used for dynamic form updates.
    """
    # Validate the date format
    try:
        selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400

    # Calculate total existing bookings for this date/session
    existing_bookings = db.session.scalar(
        sa.select(sa.func.sum(Booking.rink_count))
        .where(Booking.booking_date == selected_date)
        .where(Booking.session == session_id)
    ) or 0
    
    total_rinks = int(current_app.config.get('RINKS', 6))
    available_rinks = total_rinks - existing_bookings
    
    return jsonify({
        'total_rinks': total_rinks,
        'booked_rinks': existing_bookings,
        'available_rinks': available_rinks,
        'date': selected_date.isoformat(),
        'session': session_id
    })


@app.route('/admin/manage_events', methods=['GET', 'POST'])
@role_required('Event Manager')
def manage_events():
    """
    Route: Manage Events
    - Allows Event Managers to create and manage events.
    - Shows event form and list of bookings for selected event.
    - Allows creating bookings for events.
    """
    event_form = EventForm()
    selection_form = EventSelectionForm()
    booking_form = BookingForm()
    selected_event = None
    event_bookings = []

    # Event selection is now handled via JavaScript and URL parameters

    # Handle booking creation
    if request.method == 'POST' and 'create_booking' in request.form:
        if booking_form.validate_on_submit():
            event_id = request.form.get('event_id')
            if event_id:
                selected_event = db.session.get(Event, int(event_id))
                if selected_event:
                    # Create new booking linked to the event
                    new_booking = Booking(
                        booking_date=booking_form.booking_date.data,
                        session=booking_form.session.data,
                        rink_count=booking_form.rink_count.data,
                        priority=booking_form.priority.data,
                        event_id=selected_event.id
                    )
                    db.session.add(new_booking)
                    db.session.commit()
                    flash(f'Booking created successfully for "{selected_event.name}"!', 'success')
                    
                    # Reload the page with the selected event
                    return redirect(url_for('manage_events') + f'?event_id={selected_event.id}')
        else:
            # If booking form has errors, we need to maintain the selected event context
            event_id = request.form.get('event_id')
            if event_id:
                selected_event = db.session.get(Event, int(event_id))
                if selected_event:
                    event_form.event_id.data = selected_event.id
                    event_form.name.data = selected_event.name
                    event_form.event_type.data = selected_event.event_type
                    event_bookings = selected_event.bookings

    # Handle booking update
    if request.method == 'POST' and 'update_booking' in request.form:
        booking_id = request.form.get('booking_id')
        event_id = request.form.get('event_id')
        
        if booking_id and event_id:
            booking = db.session.get(Booking, int(booking_id))
            selected_event = db.session.get(Event, int(event_id))
            
            if booking and selected_event:
                # Update booking with form data
                booking.booking_date = datetime.strptime(request.form.get('booking_date'), '%Y-%m-%d').date()
                booking.session = int(request.form.get('session'))
                booking.rink_count = int(request.form.get('rink_count'))
                booking.priority = request.form.get('priority') or None
                
                db.session.commit()
                flash(f'Booking updated successfully!', 'success')
                
                # Reload the page with the selected event
                return redirect(url_for('manage_events') + f'?event_id={selected_event.id}')
            else:
                flash('Booking or event not found!', 'error')

    # Handle booking deletion
    if request.method == 'POST' and 'delete_booking' in request.form:
        booking_id = request.form.get('booking_id')
        event_id = request.form.get('event_id')
        
        if booking_id and event_id:
            booking = db.session.get(Booking, int(booking_id))
            selected_event = db.session.get(Event, int(event_id))
            
            if booking and selected_event:
                db.session.delete(booking)
                db.session.commit()
                flash(f'Booking deleted successfully!', 'success')
                
                # Reload the page with the selected event
                return redirect(url_for('manage_events') + f'?event_id={selected_event.id}')
            else:
                flash('Booking or event not found!', 'error')

    # Handle event create/update
    if request.method == 'POST' and 'submit' in request.form:
        if event_form.validate_on_submit():
            event_id = event_form.event_id.data
            if event_id:
                # Update existing event
                existing_event = db.session.get(Event, int(event_id))
                if existing_event:
                    existing_event.name = event_form.name.data
                    existing_event.event_type = event_form.event_type.data
                    existing_event.gender = event_form.gender.data
                    existing_event.format = event_form.format.data
                    existing_event.scoring = event_form.scoring.data
                    
                    # Update event managers (many-to-many relationship)
                    selected_manager_ids = event_form.event_managers.data
                    selected_managers = db.session.scalars(sa.select(Member).where(Member.id.in_(selected_manager_ids))).all() if selected_manager_ids else []
                    existing_event.event_managers = selected_managers
                    
                    db.session.commit()
                    flash(f'Event "{existing_event.name}" updated successfully!', 'success')
                    # Redirect with event_id to show bookings section
                    return redirect(url_for('manage_events') + f'?event_id={existing_event.id}')
                else:
                    flash('Event not found!', 'error')
                    return redirect(url_for('manage_events'))
            else:
                # Create new event
                new_event = Event(
                    name=event_form.name.data,
                    event_type=event_form.event_type.data,
                    gender=event_form.gender.data,
                    format=event_form.format.data,
                    scoring=event_form.scoring.data
                )
                db.session.add(new_event)
                db.session.flush()  # Flush to get the ID before committing
                
                # Add event managers (many-to-many relationship)
                selected_manager_ids = event_form.event_managers.data
                if selected_manager_ids:
                    selected_managers = db.session.scalars(sa.select(Member).where(Member.id.in_(selected_manager_ids))).all()
                    new_event.event_managers = selected_managers
                
                db.session.commit()
                flash(f'Event "{new_event.name}" created successfully!', 'success')
                # Redirect with event_id to show bookings section
                return redirect(url_for('manage_events') + f'?event_id={new_event.id}')

    # Handle direct event selection via URL parameter (for redirect after booking creation)
    if request.method == 'GET' and request.args.get('event_id'):
        event_id = request.args.get('event_id')
        selected_event = db.session.get(Event, int(event_id))
        if selected_event:
            event_form.event_id.data = selected_event.id
            event_form.name.data = selected_event.name
            event_form.event_type.data = selected_event.event_type
            event_form.gender.data = selected_event.gender
            event_form.format.data = selected_event.format
            event_form.scoring.data = selected_event.scoring
            event_form.event_managers.data = [manager.id for manager in selected_event.event_managers]
            event_bookings = selected_event.bookings

    return render_template('manage_events.html', 
                         event_form=event_form, 
                         selection_form=selection_form,
                         booking_form=booking_form,
                         selected_event=selected_event,
                         event_bookings=event_bookings,
                         menu_items=app.config['MENU_ITEMS'], 
                         admin_menu_items=app.config['ADMIN_MENU_ITEMS'])


@app.route('/api/event/<int:event_id>')
@login_required
def get_event(event_id):
    """
    Route: Get Event Details
    - Returns event details in JSON format for AJAX requests.
    """
    event = db.session.get(Event, event_id)
    if not event:
        return jsonify({'error': 'Event not found'}), 404
    
    return jsonify({
        'id': event.id,
        'name': event.name,
        'event_type': event.event_type,
        'event_type_name': event.get_event_type_name(),
        'gender': event.gender,
        'gender_name': event.get_gender_name(),
        'format': event.format,
        'format_name': event.get_format_name(),
        'scoring': event.scoring,
        'event_managers': [{'id': manager.id, 'name': f"{manager.firstname} {manager.lastname}"} for manager in event.event_managers],
        'created_at': event.created_at.isoformat()
    })


@app.route('/api/booking/<int:booking_id>')
@login_required
def get_booking(booking_id):
    """
    Route: Get Booking Details
    - Returns booking details in JSON format for editing.
    """
    booking = db.session.get(Booking, booking_id)
    if not booking:
        return jsonify({'error': 'Booking not found'}), 404
    
    return jsonify({
        'id': booking.id,
        'booking_date': booking.booking_date.isoformat(),
        'session': booking.session,
        'rink_count': booking.rink_count,
        'priority': booking.priority,
        'event_id': booking.event_id
    })


@app.route('/admin/edit_booking/<int:booking_id>', methods=['GET', 'POST'])
@role_required('Event Manager')
def edit_booking(booking_id):
    """
    Route: Edit Booking
    - Allows Event Managers to edit existing bookings.
    """
    booking = db.session.get(Booking, booking_id)
    if not booking:
        abort(404)
    
    form = BookingForm(obj=booking)
    
    if form.validate_on_submit():
        # Update the booking with form data
        booking.booking_date = form.booking_date.data
        booking.session = form.session.data
        booking.rink_count = form.rink_count.data
        booking.priority = form.priority.data
        
        db.session.commit()
        flash('Booking updated successfully!', 'success')
        
        # Redirect back to events management if the booking has an event
        if booking.event_id:
            return redirect(url_for('manage_events'))
        else:
            return redirect(url_for('bookings'))
    
    return render_template('booking_form.html', 
                         form=form, 
                         title=f"Edit Booking #{booking.id}",
                         menu_items=app.config['MENU_ITEMS'], 
                         admin_menu_items=app.config['ADMIN_MENU_ITEMS'])
