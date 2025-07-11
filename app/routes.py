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
    EventSelectionForm, PolicyPageForm, EditProfileForm, create_team_member_form, AddTeamForm
)
from flask_wtf import FlaskForm
from app.models import Member, Role, Post, Booking, Event, PolicyPage, EventTeam, TeamMember, BookingTeam, BookingTeamMember
from app.utils import (
    generate_reset_token, verify_reset_token, send_reset_email, 
    sanitize_filename, parse_metadata_from_markdown, sanitize_html_content,
    get_secure_post_path, get_secure_archive_path, generate_secure_filename,
    get_secure_policy_page_path, add_home_games_filter
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
    is_bootstrap = Member.is_bootstrap_mode()
    
    if form.validate_on_submit():
        # Create a new Member instance
        new_member = Member(
            username=form.username.data,
            firstname=form.firstname.data,
            lastname=form.lastname.data,
            email=form.email.data,
            phone=form.phone.data,
            password_hash=generate_password_hash(form.password.data),
            status="Full" if is_bootstrap else "Pending",  # First user gets Full status
            gender=form.gender.data,
            share_email=form.share_email.data,
            share_phone=form.share_phone.data,
            is_admin=is_bootstrap  # First user becomes admin
        )
        # Add to the database
        db.session.add(new_member)
        db.session.commit()
        
        if is_bootstrap:
            flash(f'Bootstrap admin user created: {form.firstname.data} {form.lastname.data}. You can now log in with full admin privileges.', 'success')
        else:
            flash(f'Joining application submitted for {form.firstname.data} {form.lastname.data}', 'success')
        return redirect(url_for('login'))  # Redirect to the homepage or another page
    if form.errors:
        flash(f'There are errors in your application. Please review your application and try again.', 'danger')
    return render_template('add_member.html', form=form, is_bootstrap=is_bootstrap, menu_items=app.config['MENU_ITEMS'], admin_menu_items=app.config['ADMIN_MENU_ITEMS'])


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


def _get_member_data(member, show_private_data=False):
    """
    Helper function to get member data with optional privacy filtering.
    
    This is the single source of truth for member data formatting. It ensures
    consistent behavior across all routes while allowing admin/User Manager
    access to all data and respecting privacy settings for regular users.
    
    Args:
        member: Member object from database
        show_private_data: Boolean - if True, shows all data regardless of privacy settings
                          (for admins/user managers), if False, respects privacy settings
    
    Returns:
        Dictionary with member data
    """
    return {
        'id': member.id,
        'firstname': member.firstname,
        'lastname': member.lastname,
        'username': member.username,
        'email': member.email if (show_private_data or member.share_email) else None,
        'phone': member.phone if (show_private_data or member.share_phone) else None,
        'gender': member.gender,
        'status': member.status,
        'share_email': member.share_email,
        'share_phone': member.share_phone,
        'roles': [{'id': role.id, 'name': role.name} for role in member.roles]
    }


def _search_members_base(query):
    """
    Base function to search members by various criteria.
    
    Args:
        query: Search string
        
    Returns:
        List of Member objects matching the search criteria
    """
    return db.session.scalars(sa.select(Member).where(
        (Member.username.ilike(f'%{query}%')) |
        (Member.firstname.ilike(f'%{query}%')) |
        (Member.lastname.ilike(f'%{query}%')) |
        (Member.email.ilike(f'%{query}%'))
    )).all()


@app.route('/search_members', methods=['GET'])
@login_required
def search_members():
    """
    Route: Search Members
    - Allows searching for members by username, first name, last name, or email.
    - Returns a JSON response with member details, respecting privacy settings.
    - Requires login.
    """
    query = request.args.get('q', '').strip()
    members = _search_members_base(query)
    
    # Check if current user has admin privileges (User Manager role or is_admin)
    show_private_data = (current_user.is_admin or 
                        any(role.name == 'User Manager' for role in current_user.roles))

    return jsonify({
        'members': [_get_member_data(member, show_private_data) for member in members]
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
            member.share_email = form.share_email.data
            member.share_phone = form.share_phone.data

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
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            abort(400)  # Bad request if CSRF validation fails
            
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

    # Create a simple form for CSRF protection
    csrf_form = FlaskForm()
    
    return render_template(
        'manage_roles.html',
        roles=roles,
        csrf_form=csrf_form,
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
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            abort(400)  # Bad request if CSRF validation fails
            
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

    # Create a simple form for CSRF protection
    csrf_form = FlaskForm()
    
    return render_template(
        'manage_posts.html',
        title='Manage Posts',
        posts=posts,
        today=today,
        csrf_form=csrf_form,
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
    # Exclude away games from calendar display
    booking_counts_query = sa.select(
        Booking.session,
        sa.func.sum(Booking.rink_count).label('total_rinks')
    ).where(
        Booking.booking_date == selected_date
    )
    booking_counts_query = add_home_games_filter(booking_counts_query)
    booking_counts_query = booking_counts_query.group_by(Booking.session)
    
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
    # Exclude away games from calendar display
    booking_counts_query = sa.select(
        Booking.booking_date,
        Booking.session,
        sa.func.sum(Booking.rink_count).label('total_rinks')
    ).where(
        Booking.booking_date >= start_date,
        Booking.booking_date <= end_date
    )
    booking_counts_query = add_home_games_filter(booking_counts_query)
    booking_counts_query = booking_counts_query.group_by(Booking.booking_date, Booking.session)
    
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
    # Exclude away games from rink availability calculations
    availability_query = sa.select(sa.func.sum(Booking.rink_count)).where(
        Booking.booking_date == selected_date,
        Booking.session == session_id
    )
    availability_query = add_home_games_filter(availability_query)
    existing_bookings = db.session.scalar(availability_query) or 0
    
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
                    # Validate that the event has teams before creating booking
                    if not selected_event.is_ready_for_bookings():
                        flash('Cannot create booking: Event must have at least one team defined.', 'error')
                        return redirect(url_for('manage_events', event_id=event_id))
                    
                    # Create new booking linked to the event
                    new_booking = Booking(
                        booking_date=booking_form.booking_date.data,
                        session=booking_form.session.data,
                        rink_count=booking_form.rink_count.data,
                        priority=booking_form.priority.data,
                        vs=booking_form.vs.data,
                        home_away=booking_form.home_away.data,
                        event_id=selected_event.id
                    )
                    db.session.add(new_booking)
                    db.session.flush()  # Flush to get the booking ID
                    
                    # Copy event teams to booking teams
                    from app.models import BookingTeam, BookingTeamMember
                    for event_team in selected_event.event_teams:
                        booking_team = BookingTeam(
                            booking_id=new_booking.id,
                            event_team_id=event_team.id,
                            team_name=event_team.team_name,
                            team_number=event_team.team_number
                        )
                        db.session.add(booking_team)
                        db.session.flush()  # Flush to get the booking team ID
                        
                        # Copy team members to booking team members
                        for team_member in event_team.team_members:
                            booking_team_member = BookingTeamMember(
                                booking_team_id=booking_team.id,
                                member_id=team_member.member_id,
                                position=team_member.position,
                                is_substitute=False,
                                availability_status='pending'
                            )
                            db.session.add(booking_team_member)
                    
                    db.session.commit()
                    flash(f'Booking created successfully for "{selected_event.name}" with {len(selected_event.event_teams)} teams!', 'success')
                    
                    # Reload the page with the selected event and scroll to bookings section
                    return redirect(url_for('manage_events') + f'?event_id={selected_event.id}&scroll_to=bookings-section')
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
                booking.vs = request.form.get('vs') or None
                booking.home_away = request.form.get('home_away') or None
                
                db.session.commit()
                flash(f'Booking updated successfully!', 'success')
                
                # Reload the page with the selected event and scroll to bookings section
                return redirect(url_for('manage_events') + f'?event_id={selected_event.id}&scroll_to=bookings-section')
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
                
                # Reload the page with the selected event and scroll to bookings section
                return redirect(url_for('manage_events') + f'?event_id={selected_event.id}&scroll_to=bookings-section')
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
                    
                    # Teams are now managed individually through separate routes
                    
                    db.session.commit()
                    flash(f'Event "{existing_event.name}" updated successfully!', 'success')
                    # Redirect with event_id to show teams section
                    return redirect(url_for('manage_events') + f'?event_id={existing_event.id}&scroll_to=teams-section')
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
                flash(f'Event "{new_event.name}" created successfully! Now add teams to this event.', 'success')
                # Redirect with event_id to show teams section
                return redirect(url_for('manage_events') + f'?event_id={new_event.id}&scroll_to=teams-section')

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
                         event_teams=selected_event.event_teams if selected_event else [],
                         team_positions=app.config.get('TEAM_POSITIONS', {}),
                         can_create_bookings=selected_event.is_ready_for_bookings() if selected_event else False,
                         menu_items=app.config['MENU_ITEMS'], 
                         admin_menu_items=app.config['ADMIN_MENU_ITEMS'])


@app.route('/my_games', methods=['GET', 'POST'])
@login_required
def my_games():
    """
    Route: My Games Dashboard
    - Shows the current user's upcoming booking team assignments
    - Allows players to confirm availability for upcoming games
    - Displays game details including event, date, session, and team position
    """
    from datetime import date
    
    # Get all booking team assignments for the current user (past and future)
    all_assignments = db.session.scalars(
        sa.select(BookingTeamMember)
        .join(BookingTeam)
        .join(Booking)
        .join(Event)
        .where(
            BookingTeamMember.member_id == current_user.id
        )
        .order_by(Booking.booking_date, Booking.session)
    ).all()
    
    # Handle availability confirmation
    if request.method == 'POST':
        assignment_id = request.form.get('assignment_id')
        action = request.form.get('action')
        
        if assignment_id and action in ['confirm_available', 'confirm_unavailable']:
            assignment = db.session.get(BookingTeamMember, int(assignment_id))
            if assignment and assignment.member_id == current_user.id and assignment.availability_status == 'pending':
                if action == 'confirm_available':
                    assignment.availability_status = 'available'
                    assignment.confirmed_at = datetime.utcnow()
                    flash('Availability confirmed successfully!', 'success')
                elif action == 'confirm_unavailable':
                    assignment.availability_status = 'unavailable'
                    assignment.confirmed_at = datetime.utcnow()
                    flash('Unavailability confirmed. The event organizer will arrange a substitute.', 'info')
                
                db.session.commit()
            else:
                flash('Unable to update availability for this assignment.', 'error')
        
        return redirect(url_for('my_games'))
    
    # Create a simple form for CSRF protection
    csrf_form = FlaskForm()
    
    return render_template('my_games.html',
                         assignments=all_assignments,
                         csrf_form=csrf_form,
                         today=date.today(),
                         config=app.config,
                         menu_items=app.config['MENU_ITEMS'],
                         admin_menu_items=app.config['ADMIN_MENU_ITEMS'])


@app.route('/manage_teams/<int:booking_id>', methods=['GET', 'POST'])
@role_required('Event Manager')
def manage_booking_teams(booking_id):
    """
    Route: Manage Booking Teams
    - Allows Event Managers to view and modify teams for a specific booking
    - Handles substitutions and team member assignments
    - Shows availability status of all team members
    """
    booking = db.session.get(Booking, booking_id)
    if not booking:
        abort(404)
    
    # Check if current user is an event manager for this event
    if not current_user.is_admin:
        user_role_names = [role.name for role in current_user.roles]
        if 'Event Manager' not in user_role_names:
            abort(403)
        # Additional check: is user an event manager for this specific event?
        if current_user not in booking.event.event_managers:
            abort(403)
    
    # Handle substitution
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'substitute_player':
            booking_team_member_id = request.form.get('booking_team_member_id')
            new_member_id = request.form.get('new_member_id')
            
            if booking_team_member_id and new_member_id:
                booking_team_member = db.session.get(BookingTeamMember, int(booking_team_member_id))
                new_member = db.session.get(Member, int(new_member_id))
                
                if booking_team_member and new_member:
                    # Log the substitution
                    substitution_log = {
                        'timestamp': datetime.utcnow().isoformat(),
                        'action': 'substitution',
                        'original_player': f"{booking_team_member.member.firstname} {booking_team_member.member.lastname}",
                        'substitute_player': f"{new_member.firstname} {new_member.lastname}",
                        'position': booking_team_member.position,
                        'made_by': f"{current_user.firstname} {current_user.lastname}",
                        'reason': request.form.get('reason', 'No reason provided')
                    }
                    
                    # Update the booking team member
                    booking_team_member.member_id = new_member.id
                    booking_team_member.is_substitute = True
                    booking_team_member.substituted_at = datetime.utcnow()
                    booking_team_member.availability_status = 'pending'  # New player needs to confirm
                    booking_team_member.confirmed_at = None
                    
                    # Update the substitution log on the booking team
                    import json
                    booking_team = booking_team_member.booking_team
                    current_log = json.loads(booking_team.substitution_log or '[]')
                    current_log.append(substitution_log)
                    booking_team.substitution_log = json.dumps(current_log)
                    
                    db.session.commit()
                    flash(f'Successfully substituted {substitution_log["original_player"]} with {substitution_log["substitute_player"]} for {booking_team_member.position}', 'success')
                else:
                    flash('Invalid player selection for substitution', 'error')
        
        return redirect(url_for('manage_booking_teams', booking_id=booking_id))
    
    # Get available members for substitutions (excluding current team members)
    current_member_ids = [btm.member_id for team in booking.booking_teams for btm in team.booking_team_members]
    available_members = db.session.scalars(
        sa.select(Member)
        .where(
            Member.status.in_(['Full', 'Social', 'Life']),
            ~Member.id.in_(current_member_ids)
        )
        .order_by(Member.firstname, Member.lastname)
    ).all()
    
    # Create a simple form for CSRF protection
    csrf_form = FlaskForm()
    
    return render_template('manage_booking_teams.html',
                         booking=booking,
                         available_members=available_members,
                         csrf_form=csrf_form,
                         team_positions=app.config.get('TEAM_POSITIONS', {}),
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
        booking.vs = form.vs.data
        booking.home_away = form.home_away.data
        
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


# Policy Page Management Routes

@app.route('/policy/<slug>')
def view_policy_page(slug):
    """
    Route: View Policy Page
    - Displays a policy page by its slug.
    - Only shows active policy pages.
    """
    policy_page = db.session.scalar(
        sa.select(PolicyPage).where(PolicyPage.slug == slug, PolicyPage.is_active == True)
    )
    
    if not policy_page:
        abort(404)
    
    # Read the HTML content from secure storage
    html_path = get_secure_policy_page_path(policy_page.html_filename)
    if not html_path or not os.path.exists(html_path):
        abort(404)
    
    with open(html_path, 'r') as html_file:
        content = html_file.read()
    
    return render_template(
        'view_policy_page.html',
        policy_page=policy_page,
        content=content,
        menu_items=app.config['MENU_ITEMS'],
        admin_menu_items=app.config['ADMIN_MENU_ITEMS']
    )


@app.route('/admin/manage_policy_pages', methods=['GET', 'POST'])
@admin_required
def manage_policy_pages():
    """
    Route: Manage Policy Pages
    - Allows admins to view and manage all policy pages.
    """
    policy_pages = db.session.scalars(
        sa.select(PolicyPage).order_by(PolicyPage.sort_order, PolicyPage.title)
    ).all()
    
    # Create a simple form for CSRF protection
    csrf_form = FlaskForm()
    
    return render_template(
        'manage_policy_pages.html',
        policy_pages=policy_pages,
        csrf_form=csrf_form,
        menu_items=app.config['MENU_ITEMS'],
        admin_menu_items=app.config['ADMIN_MENU_ITEMS']
    )


@app.route('/admin/create_policy_page', methods=['GET', 'POST'])
@admin_required
def create_policy_page():
    """
    Route: Create Policy Page
    - Allows admins to create a new policy page.
    """
    form = PolicyPageForm()
    
    if form.validate_on_submit():
        # Check if slug already exists
        existing_page = db.session.scalar(
            sa.select(PolicyPage).where(PolicyPage.slug == form.slug.data)
        )
        if existing_page:
            flash('A policy page with this URL slug already exists. Please choose a different slug.', 'error')
            return render_template('policy_page_form.html', form=form, title="Create Policy Page",
                                 menu_items=app.config['MENU_ITEMS'], admin_menu_items=app.config['ADMIN_MENU_ITEMS'])
        
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
        
        # Save content to secure storage
        policy_dir = current_app.config['POLICY_PAGES_STORAGE_PATH']
        os.makedirs(policy_dir, exist_ok=True)
        markdown_path = get_secure_policy_page_path(markdown_filename)
        html_path = get_secure_policy_page_path(html_filename)
        
        # Validate secure paths
        if not markdown_path or not html_path:
            abort(400)  # Bad request for invalid filenames
        
        # Create metadata dictionary and serialize to YAML
        metadata_dict = {
            'title': policy_page.title,
            'slug': policy_page.slug,
            'description': policy_page.description,
            'is_active': policy_page.is_active,
            'show_in_footer': policy_page.show_in_footer,
            'sort_order': policy_page.sort_order,
            'author': current_user.username
        }
        metadata = "---\n" + yaml.dump(metadata_dict, default_flow_style=False) + "---\n"
        with open(markdown_path, 'w') as md_file:
            md_file.write(metadata + '\n' + form.content.data)
        
        # Convert Markdown to HTML and save
        html_content = markdown(form.content.data, extras=["tables"])
        with open(html_path, 'w') as html_file:
            html_file.write(html_content)
        
        flash('Policy page created successfully!', 'success')
        return redirect(url_for('manage_policy_pages'))
    
    return render_template('policy_page_form.html', form=form, title="Create Policy Page",
                         menu_items=app.config['MENU_ITEMS'], admin_menu_items=app.config['ADMIN_MENU_ITEMS'])


@app.route('/admin/edit_policy_page/<int:policy_page_id>', methods=['GET', 'POST'])
@admin_required
def edit_policy_page(policy_page_id):
    """
    Route: Edit Policy Page
    - Allows admins to edit an existing policy page.
    """
    policy_page = db.session.get(PolicyPage, policy_page_id)
    if not policy_page:
        abort(404)
    
    form = PolicyPageForm()
    
    if form.validate_on_submit():
        # Check if slug already exists (excluding current page)
        existing_page = db.session.scalar(
            sa.select(PolicyPage).where(PolicyPage.slug == form.slug.data, PolicyPage.id != policy_page_id)
        )
        if existing_page:
            flash('A policy page with this URL slug already exists. Please choose a different slug.', 'error')
            return render_template('policy_page_form.html', form=form, title="Edit Policy Page",
                                 menu_items=app.config['MENU_ITEMS'], admin_menu_items=app.config['ADMIN_MENU_ITEMS'])
        
        # Update policy page metadata
        policy_page.title = form.title.data
        policy_page.slug = form.slug.data
        policy_page.description = form.description.data
        policy_page.is_active = form.is_active.data
        policy_page.show_in_footer = form.show_in_footer.data
        policy_page.sort_order = form.sort_order.data or 0
        db.session.commit()
        
        # Update content files
        markdown_path = get_secure_policy_page_path(policy_page.markdown_filename)
        html_path = get_secure_policy_page_path(policy_page.html_filename)
        
        # Validate secure paths
        if not markdown_path or not html_path:
            abort(400)  # Bad request for invalid filenames
        
        # Create metadata dictionary and serialize to YAML
        metadata_dict = {
            'title': policy_page.title,
            'slug': policy_page.slug,
            'description': policy_page.description,
            'is_active': policy_page.is_active,
            'show_in_footer': policy_page.show_in_footer,
            'sort_order': policy_page.sort_order,
            'author': current_user.username
        }
        metadata = "---\n" + yaml.dump(metadata_dict, default_flow_style=False) + "---\n"
        with open(markdown_path, 'w') as md_file:
            md_file.write(metadata + '\n' + form.content.data)
        
        # Convert Markdown to HTML and save
        html_content = markdown(form.content.data, extras=["tables"])
        with open(html_path, 'w') as html_file:
            html_file.write(html_content)
        
        flash('Policy page updated successfully!', 'success')
        return redirect(url_for('manage_policy_pages'))
    
    # Pre-populate form with existing data
    if request.method == 'GET':
        form.title.data = policy_page.title
        form.slug.data = policy_page.slug
        form.description.data = policy_page.description
        form.is_active.data = policy_page.is_active
        form.show_in_footer.data = policy_page.show_in_footer
        form.sort_order.data = policy_page.sort_order
        
        # Load content from markdown file
        markdown_path = get_secure_policy_page_path(policy_page.markdown_filename)
        if markdown_path and os.path.exists(markdown_path):
            with open(markdown_path, 'r') as md_file:
                content = md_file.read()
                # Remove YAML front matter
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        form.content.data = parts[2].strip()
                    else:
                        form.content.data = content
                else:
                    form.content.data = content
    
    return render_template('policy_page_form.html', form=form, title="Edit Policy Page",
                         menu_items=app.config['MENU_ITEMS'], admin_menu_items=app.config['ADMIN_MENU_ITEMS'])


@app.route('/admin/delete_policy_page/<int:policy_page_id>', methods=['POST'])
@admin_required
def delete_policy_page(policy_page_id):
    """
    Route: Delete Policy Page
    - Allows admins to delete a policy page and its associated files.
    """
    policy_page = db.session.get(PolicyPage, policy_page_id)
    if not policy_page:
        abort(404)
    
    # Delete files from secure storage
    markdown_path = get_secure_policy_page_path(policy_page.markdown_filename)
    html_path = get_secure_policy_page_path(policy_page.html_filename)
    
    if markdown_path and os.path.exists(markdown_path):
        os.remove(markdown_path)
    if html_path and os.path.exists(html_path):
        os.remove(html_path)
    
    # Delete from database
    db.session.delete(policy_page)
    db.session.commit()
    
    flash('Policy page deleted successfully!', 'success')
    return redirect(url_for('manage_policy_pages'))


@app.route('/admin/edit_event_team/<int:team_id>', methods=['GET', 'POST'])
@role_required('Event Manager')
def edit_event_team(team_id):
    """
    Route: Edit Event Team
    - Allows Event Managers to assign players to team positions.
    - Updates the team member assignments for an event team.
    """
    team = db.session.get(EventTeam, team_id)
    if not team:
        abort(404)
    
    # Check if user has permission to manage this event
    if not current_user.is_admin and current_user not in team.event.event_managers:
        abort(403)
    
    TeamMemberForm = create_team_member_form(team.event.format)
    form = TeamMemberForm()
    
    if form.validate_on_submit():
        # Clear existing team members
        existing_members = db.session.scalars(
            sa.select(TeamMember).where(TeamMember.event_team_id == team.id)
        ).all()
        for member in existing_members:
            db.session.delete(member)
        
        # Update team name
        team.team_name = form.team_name.data
        
        # Add new team members based on form data
        team_positions = current_app.config.get('TEAM_POSITIONS', {})
        positions = team_positions.get(team.event.format, [])
        
        for position in positions:
            field_name = f"position_{position.lower().replace(' ', '_')}"
            member_id = getattr(form, field_name).data
            
            if member_id and member_id > 0:  # Skip empty selections
                team_member = TeamMember(
                    event_team_id=team.id,
                    member_id=member_id,
                    position=position
                )
                db.session.add(team_member)
        
        db.session.commit()
        flash(f'Team "{team.team_name}" updated successfully!', 'success')
        return redirect(url_for('manage_events', event_id=team.event_id))
    
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
    
    return render_template('edit_event_team.html', 
                         form=form, 
                         team=team,
                         event=team.event,
                         title=f"Edit {team.team_name}",
                         menu_items=app.config['MENU_ITEMS'], 
                         admin_menu_items=app.config['ADMIN_MENU_ITEMS'])


@app.route('/admin/add_event_team/<int:event_id>', methods=['GET', 'POST'])
@role_required('Event Manager')
def add_event_team(event_id):
    """
    Route: Add Event Team
    - Allows Event Managers to add a new team to an event.
    - Creates a team with a custom name chosen by the user.
    """
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    
    # Check if user has permission to manage this event
    if not current_user.is_admin and current_user not in event.event_managers:
        abort(403)
    
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
        
        flash(f'Team "{new_team.team_name}" added successfully!', 'success')
        return redirect(url_for('manage_events', event_id=event_id) + '&scroll_to=teams-section')
    
    return render_template('add_event_team.html', 
                         form=form, 
                         event=event,
                         title=f"Add Team to {event.name}",
                         menu_items=app.config['MENU_ITEMS'], 
                         admin_menu_items=app.config['ADMIN_MENU_ITEMS'])


@app.route('/admin/delete_event_team/<int:team_id>', methods=['POST'])
@role_required('Event Manager')
def delete_event_team(team_id):
    """
    Route: Delete Event Team
    - Allows Event Managers to delete an event team.
    - Also deletes all associated team members and booking teams.
    """
    team = db.session.get(EventTeam, team_id)
    if not team:
        abort(404)
    
    # Check if user has permission to manage this event
    if not current_user.is_admin and current_user not in team.event.event_managers:
        abort(403)
    
    event_id = team.event_id
    team_name = team.team_name
    
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
    
    if booking_teams_count > 0:
        flash(f'Team "{team_name}" deleted. Existing bookings remain unchanged.', 'info')
    else:
        flash(f'Team "{team_name}" deleted successfully!', 'success')
    
    return redirect(url_for('manage_events', event_id=event_id) + '&scroll_to=teams-section')


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """
    Route: Edit Profile
    - Allows users to edit their own profile information.
    - Users can update personal details and privacy settings.
    """
    form = EditProfileForm(current_user.email)
    
    if form.validate_on_submit():
        current_user.firstname = form.firstname.data
        current_user.lastname = form.lastname.data
        current_user.email = form.email.data
        current_user.phone = form.phone.data
        current_user.gender = form.gender.data
        current_user.share_email = form.share_email.data
        current_user.share_phone = form.share_phone.data
        
        db.session.commit()
        flash('Your profile has been updated successfully!', 'success')
        return redirect(url_for('edit_profile'))
    
    # Pre-populate form with current user data
    elif request.method == 'GET':
        form.firstname.data = current_user.firstname
        form.lastname.data = current_user.lastname
        form.email.data = current_user.email
        form.phone.data = current_user.phone
        form.gender.data = current_user.gender
        form.share_email.data = current_user.share_email
        form.share_phone.data = current_user.share_phone
    
    return render_template('edit_profile.html', form=form,
                         menu_items=app.config['MENU_ITEMS'], 
                         admin_menu_items=app.config['ADMIN_MENU_ITEMS'])
