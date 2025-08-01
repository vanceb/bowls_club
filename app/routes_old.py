# Standard library imports
import csv
import io
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
from app import db, limiter
from flask import current_app
from app.audit import (
    audit_log_create, audit_log_update, audit_log_delete, audit_log_bulk_operation,
    audit_log_authentication, audit_log_security_event, get_model_changes
)
from app.forms import (
    LoginForm, MemberForm, EditMemberForm, RequestResetForm, 
    ResetPasswordForm, PasswordResetForm, WritePostForm, BookingForm, EventForm, 
    EventSelectionForm, PolicyPageForm, EditProfileForm, create_team_member_form, AddTeamForm,
    ImportUsersForm, RollUpBookingForm, RollUpResponseForm
)
from flask_wtf import FlaskForm
from app.models import Member, Role, Post, Booking, Event, PolicyPage, EventTeam, TeamMember, BookingTeam, BookingTeamMember, BookingPlayer
from app.utils import (
    generate_reset_token, verify_reset_token, send_reset_email, 
    sanitize_filename, parse_metadata_from_markdown, sanitize_html_content,
    get_secure_post_path, get_secure_archive_path, generate_secure_filename,
    get_secure_policy_page_path, add_home_games_filter, find_orphaned_policy_pages,
    recover_orphaned_policy_page
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
        'last_seen': member.last_seen.strftime('%Y-%m-%d') if member.last_seen else 'Never',
        'lockout': member.lockout,
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
            return redirect(url_for('manage_members'))
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
            return redirect(url_for('manage_members'))

    return render_template(
        'edit_member.html',
        form=form,
        member=member,
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
    - Implements timing attack prevention to avoid user enumeration.
    """
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RequestResetForm()
    if form.validate_on_submit():
        import time
        import secrets
        
        # Implement consistent timing to prevent user enumeration
        start_time = time.time()
        
        user = db.session.scalar(sa.select(Member).where(Member.email == form.email.data))
        if user:
            token = generate_reset_token(user.email)
            reset_url = url_for('pw_reset', token=token, _external=True)
            send_reset_email(user.email, reset_url)
        else:
            # Perform dummy operations to maintain consistent timing
            # Generate a dummy token to simulate the same work
            dummy_email = f"dummy{secrets.token_hex(8)}@example.com"
            generate_reset_token(dummy_email)
        
        # Ensure minimum processing time to prevent timing attacks
        min_processing_time = 0.5  # 500ms minimum
        elapsed_time = time.time() - start_time
        if elapsed_time < min_processing_time:
            time.sleep(min_processing_time - elapsed_time)

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
            
            # Audit log the password reset
            audit_log_authentication('PASSWORD_RESET', user.username, True)
            
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

        # Audit log the post creation
        audit_log_create('Post', post.id, f'Created post: {post.title}',
                        {'publish_on': post.publish_on.isoformat(), 'expires_on': post.expires_on.isoformat()})

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
            audit_log_bulk_operation('BULK_DELETE', 'Post', len(deleted_posts), 
                                   f'Deleted {len(deleted_posts)} posts: {", ".join(deleted_posts)}')
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
    - Returns detailed booking information per session for a date range in JSON format.
    - Used for the calendar layout with dates as rows and sessions as columns.
    """
    # Validate the date formats
    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400

    # Query individual bookings with details for the date range
    # Exclude away games from calendar display
    bookings_query = sa.select(
        Booking.booking_date,
        Booking.session,
        Booking.rink_count,
        Booking.vs,
        Booking.priority,
        Booking.booking_type,
        Booking.organizer_notes,
        Event.name.label('event_name'),
        Event.event_type.label('event_type'),
        Member.firstname.label('organizer_firstname'),
        Member.lastname.label('organizer_lastname')
    ).outerjoin(Event, Booking.event_id == Event.id).outerjoin(
        Member, Booking.organizer_id == Member.id
    ).where(
        Booking.booking_date >= start_date,
        Booking.booking_date <= end_date
    )
    bookings_query = add_home_games_filter(bookings_query)
    bookings_query = bookings_query.order_by(Booking.booking_date, Booking.session)
    
    bookings_result = db.session.execute(bookings_query).all()

    # Prepare data structure: {date: {session: [booking_details]}}
    bookings_data = {}
    for booking in bookings_result:
        date_str = booking.booking_date.isoformat()
        session = booking.session
        
        if date_str not in bookings_data:
            bookings_data[date_str] = {}
        if session not in bookings_data[date_str]:
            bookings_data[date_str][session] = []
            
        # Create booking detail object
        if booking.booking_type == 'rollup':
            booking_detail = {
                'event_name': f'Roll-Up ({booking.organizer_firstname} {booking.organizer_lastname})',
                'vs': None,
                'rink_count': booking.rink_count,
                'priority': booking.priority,
                'booking_type': 'rollup',
                'event_type': None,
                'organizer_notes': booking.organizer_notes
            }
        else:
            booking_detail = {
                'event_name': booking.event_name,
                'vs': booking.vs,
                'rink_count': booking.rink_count,
                'priority': booking.priority,
                'booking_type': 'event',
                'event_type': booking.event_type
            }
        
        bookings_data[date_str][session].append(booking_detail)

    rinks = current_app.config['RINKS']
    sessions = current_app.config['DAILY_SESSIONS']
    event_types = current_app.config['EVENT_TYPES']

    return jsonify({
        'bookings': bookings_data, 
        'rinks': rinks, 
        'sessions': sessions,
        'event_types': event_types
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
                    team_count = 0
                    member_count = 0
                    
                    for event_team in selected_event.event_teams:
                        booking_team = BookingTeam(
                            booking_id=new_booking.id,
                            event_team_id=event_team.id,
                            team_name=event_team.team_name,
                            team_number=event_team.team_number
                        )
                        db.session.add(booking_team)
                        db.session.flush()  # Flush to get the booking team ID
                        team_count += 1
                        
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
                            member_count += 1
                    
                    db.session.commit()
                    
                    # Audit log the booking creation
                    audit_log_create('Booking', new_booking.id, 
                                   f'Created booking for event "{selected_event.name}" on {new_booking.booking_date}',
                                   {'event_id': selected_event.id, 'session': new_booking.session, 
                                    'rink_count': new_booking.rink_count, 'teams_created': team_count, 
                                    'members_assigned': member_count})
                    
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
                # Capture changes for audit log
                old_booking_date = booking.booking_date
                old_session = booking.session
                old_rink_count = booking.rink_count
                old_priority = booking.priority
                old_vs = booking.vs
                old_home_away = booking.home_away
                
                # Update booking with form data
                booking.booking_date = datetime.strptime(request.form.get('booking_date'), '%Y-%m-%d').date()
                booking.session = int(request.form.get('session'))
                booking.rink_count = int(request.form.get('rink_count'))
                booking.priority = request.form.get('priority') or None
                booking.vs = request.form.get('vs') or None
                booking.home_away = request.form.get('home_away') or None
                
                # Build changes dictionary
                changes = {}
                if old_booking_date != booking.booking_date:
                    changes['booking_date'] = old_booking_date.isoformat()
                if old_session != booking.session:
                    changes['session'] = old_session
                if old_rink_count != booking.rink_count:
                    changes['rink_count'] = old_rink_count
                if old_priority != booking.priority:
                    changes['priority'] = old_priority
                if old_vs != booking.vs:
                    changes['vs'] = old_vs
                if old_home_away != booking.home_away:
                    changes['home_away'] = old_home_away
                
                db.session.commit()
                
                # Audit log the booking update
                audit_log_update('Booking', booking.id, 
                               f'Updated booking for event "{selected_event.name}" on {booking.booking_date}',
                               changes)
                
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
                # Capture booking info for audit log
                booking_info = f'event "{selected_event.name}" on {booking.booking_date}'
                
                db.session.delete(booking)
                db.session.commit()
                
                # Audit log the booking deletion
                audit_log_delete('Booking', booking_id, f'Deleted booking for {booking_info}')
                
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
                    # Capture changes for audit log
                    changes = get_model_changes(existing_event, {
                        'name': event_form.name.data,
                        'event_type': event_form.event_type.data,
                        'gender': event_form.gender.data,
                        'format': event_form.format.data,
                        'scoring': event_form.scoring.data
                    })
                    
                    # Update event fields
                    existing_event.name = event_form.name.data
                    existing_event.event_type = event_form.event_type.data
                    existing_event.gender = event_form.gender.data
                    existing_event.format = event_form.format.data
                    existing_event.scoring = event_form.scoring.data
                    
                    # Update event managers (many-to-many relationship)
                    selected_manager_ids = event_form.event_managers.data
                    selected_managers = db.session.scalars(sa.select(Member).where(Member.id.in_(selected_manager_ids))).all() if selected_manager_ids else []
                    old_managers = [f"{mgr.firstname} {mgr.lastname}" for mgr in existing_event.event_managers]
                    new_managers = [f"{mgr.firstname} {mgr.lastname}" for mgr in selected_managers]
                    if old_managers != new_managers:
                        changes['event_managers'] = old_managers
                    existing_event.event_managers = selected_managers
                    
                    # Teams are now managed individually through separate routes
                    
                    db.session.commit()
                    
                    # Audit log the event update
                    audit_log_update('Event', existing_event.id, 
                                   f'Updated event: {existing_event.name}', changes)
                    
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
                event_managers = []
                if selected_manager_ids:
                    selected_managers = db.session.scalars(sa.select(Member).where(Member.id.in_(selected_manager_ids))).all()
                    new_event.event_managers = selected_managers
                    event_managers = [f"{mgr.firstname} {mgr.lastname}" for mgr in selected_managers]
                
                db.session.commit()
                
                # Audit log the event creation
                audit_log_create('Event', new_event.id, 
                               f'Created event: {new_event.name}',
                               {'event_type': new_event.event_type, 'gender': new_event.gender, 
                                'format': new_event.format, 'event_managers': event_managers})
                
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
    
    # Get all roll-up invitations for the current user
    roll_up_invitations = db.session.scalars(
        sa.select(BookingPlayer)
        .join(Booking)
        .where(
            BookingPlayer.member_id == current_user.id,
            Booking.booking_type == 'rollup'
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
                    
                    # Audit log the availability confirmation
                    audit_log_update('BookingTeamMember', assignment.id, 
                                   f'Confirmed availability for booking on {assignment.booking_team.booking.booking_date}',
                                   {'availability_status': 'pending'})
                    
                    flash('Availability confirmed successfully!', 'success')
                elif action == 'confirm_unavailable':
                    assignment.availability_status = 'unavailable'
                    assignment.confirmed_at = datetime.utcnow()
                    
                    # Audit log the unavailability confirmation
                    audit_log_update('BookingTeamMember', assignment.id, 
                                   f'Confirmed unavailability for booking on {assignment.booking_team.booking.booking_date}',
                                   {'availability_status': 'pending'})
                    
                    flash('Unavailability confirmed. The event organizer will arrange a substitute.', 'info')
                
                db.session.commit()
            else:
                flash('Unable to update availability for this assignment.', 'error')
        
        return redirect(url_for('my_games'))
    
    # Create a simple form for CSRF protection
    csrf_form = FlaskForm()
    
    return render_template('my_games.html',
                         assignments=all_assignments,
                         roll_up_invitations=roll_up_invitations,
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
                    
                    # Audit log the substitution
                    audit_log_update('BookingTeamMember', booking_team_member.id, 
                                   f'Substituted {substitution_log["original_player"]} with {substitution_log["substitute_player"]} for {booking_team_member.position}',
                                   {'original_member_id': booking_team_member.member_id, 'reason': substitution_log['reason']})
                    
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
    - Provides functionality to scan for and recover orphaned policy page files.
    """
    policy_pages = db.session.scalars(
        sa.select(PolicyPage).order_by(PolicyPage.sort_order, PolicyPage.title)
    ).all()
    
    # Check for orphaned policy pages if requested
    orphaned_pages = []
    show_orphaned = request.args.get('show_orphaned') == 'true'
    if show_orphaned:
        orphaned_pages = find_orphaned_policy_pages()
    
    # Create a simple form for CSRF protection
    csrf_form = FlaskForm()
    
    return render_template(
        'manage_policy_pages.html',
        policy_pages=policy_pages,
        orphaned_pages=orphaned_pages,
        show_orphaned=show_orphaned,
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
        
        # Capture changes for audit log
        changes = get_model_changes(policy_page, {
            'title': form.title.data,
            'slug': form.slug.data,
            'description': form.description.data,
            'is_active': form.is_active.data,
            'show_in_footer': form.show_in_footer.data,
            'sort_order': form.sort_order.data or 0
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
    
    # Capture policy page info for audit log
    policy_page_info = f'{policy_page.title} (slug: {policy_page.slug})'
    
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
    
    # Audit log the policy page deletion
    audit_log_delete('PolicyPage', policy_page_id, f'Deleted policy page: {policy_page_info}')
    
    flash('Policy page deleted successfully!', 'success')
    return redirect(url_for('manage_policy_pages'))


@app.route('/admin/recover_policy_page/<filename>', methods=['POST'])
@admin_required
def recover_policy_page(filename):
    """
    Route: Recover Orphaned Policy Page
    - Allows admins to recover orphaned policy page files by adding them to the database.
    """
    # Validate CSRF token
    csrf_form = FlaskForm()
    if not csrf_form.validate_on_submit():
        abort(400)  # Bad request if CSRF validation fails
    
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
    
    return redirect(url_for('manage_policy_pages', show_orphaned='true'))


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
        # Capture existing team members for audit log
        existing_members = db.session.scalars(
            sa.select(TeamMember).where(TeamMember.event_team_id == team.id)
        ).all()
        old_members = [f"{member.member.firstname} {member.member.lastname} ({member.position})" 
                      for member in existing_members]
        
        # Clear existing team members
        for member in existing_members:
            db.session.delete(member)
        
        # Update team name
        old_team_name = team.team_name
        team.team_name = form.team_name.data
        
        # Add new team members based on form data
        team_positions = current_app.config.get('TEAM_POSITIONS', {})
        positions = team_positions.get(team.event.format, [])
        new_members = []
        
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
                member_obj = db.session.get(Member, member_id)
                new_members.append(f"{member_obj.firstname} {member_obj.lastname} ({position})")
        
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
        
        # Audit log the team creation
        audit_log_create('EventTeam', new_team.id, 
                        f'Created team: {new_team.team_name} for event "{event.name}"',
                        {'team_number': next_team_number})
        
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
        # Capture changes for audit log
        changes = get_model_changes(current_user, {
            'firstname': form.firstname.data,
            'lastname': form.lastname.data,
            'email': form.email.data,
            'phone': form.phone.data,
            'gender': form.gender.data,
            'share_email': form.share_email.data,
            'share_phone': form.share_phone.data
        })
        
        current_user.firstname = form.firstname.data
        current_user.lastname = form.lastname.data
        current_user.email = form.email.data
        current_user.phone = form.phone.data
        current_user.gender = form.gender.data
        current_user.share_email = form.share_email.data
        current_user.share_phone = form.share_phone.data
        
        db.session.commit()
        
        # Audit log the profile update
        audit_log_update('Member', current_user.id, f'Updated profile for {current_user.username}', changes)
        
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


@app.route('/reset_password', methods=['GET', 'POST'])
@login_required
def reset_password():
    """
    Route: Reset Password
    - Allows users to reset their own password.
    - Does not require current password for security simplicity.
    """
    form = PasswordResetForm()
    
    if form.validate_on_submit():
        current_user.set_password(form.new_password.data)
        db.session.commit()
        
        # Audit log the password change
        audit_log_update('Member', current_user.id, 
                        f'Password reset for user: {current_user.username}', 
                        {'password': 'changed'})
        
        flash('Your password has been reset successfully!', 'success')
        return redirect(url_for('edit_profile'))
    
    return render_template('reset_password.html', form=form,
                         form_title='Reset Your Password',
                         form_action=url_for('reset_password'),
                         menu_items=app.config['MENU_ITEMS'], 
                         admin_menu_items=app.config['ADMIN_MENU_ITEMS'])


@app.route('/admin/reset_member_password/<int:member_id>', methods=['GET', 'POST'])
@role_required('User Manager')
def admin_reset_password(member_id):
    """
    Route: Admin Reset Member Password
    - Allows admin/user manager to reset any user's password.
    - Requires User Manager role or admin privileges.
    """
    member = db.session.get(Member, member_id)
    if not member:
        abort(404)
    
    form = PasswordResetForm()
    
    if form.validate_on_submit():
        member.set_password(form.new_password.data)
        db.session.commit()
        
        # Audit log the password reset
        audit_log_update('Member', member.id, 
                        f'Password reset by admin for user: {member.username}', 
                        {'password': 'reset_by_admin'})
        
        flash(f'Password reset successfully for {member.firstname} {member.lastname}!', 'success')
        return redirect(url_for('edit_member', member_id=member.id))
    
    return render_template('admin_reset_password.html', form=form, member=member,
                         form_title=f'Reset Password for {member.firstname} {member.lastname}',
                         form_action=url_for('admin_reset_password', member_id=member.id),
                         menu_items=app.config['MENU_ITEMS'], 
                         admin_menu_items=app.config['ADMIN_MENU_ITEMS'])


@app.route('/import_users', methods=['GET', 'POST'])
@admin_required
def import_users():
    """
    Route: Import Users from CSV
    - Admin-only route for importing user data from CSV files.
    - Required columns: firstname, lastname, email, phone
    - Optional columns: username, gender
    - Imported users get 'pending' status and no roles
    """
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
                return render_template('import_users.html', form=form, results=results,
                                     menu_items=app.config['MENU_ITEMS'],
                                     admin_menu_items=app.config['ADMIN_MENU_ITEMS'])
            
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
    
    return render_template('import_users.html', form=form, results=results,
                         menu_items=app.config['MENU_ITEMS'],
                         admin_menu_items=app.config['ADMIN_MENU_ITEMS'])


# Roll-up booking routes
@app.route('/rollup/book', methods=['GET', 'POST'])
@login_required
def book_rollup():
    """
    Route: Create Roll-Up Booking
    - Allows users to create roll-up bookings with invited players
    - Validates date limits, rink availability, and player counts
    """
    form = RollUpBookingForm()
    
    if form.validate_on_submit():
        # Create the roll-up booking
        new_booking = Booking(
            booking_date=form.booking_date.data,
            session=form.session.data,
            rink_count=1,  # Roll-ups always use 1 rink
            booking_type='rollup',
            organizer_id=current_user.id,
            organizer_notes=form.organizer_notes.data
        )
        
        db.session.add(new_booking)
        db.session.flush()  # Get the booking ID
        
        # Add the organizer as a confirmed player
        organizer_player = BookingPlayer(
            booking_id=new_booking.id,
            member_id=current_user.id,
            status='confirmed',
            invited_by=current_user.id,
            response_at=datetime.utcnow()
        )
        db.session.add(organizer_player)
        
        # Add invited players as pending
        invited_count = 0
        for player_id in form.invited_players.data:
            if player_id != current_user.id:  # Don't invite yourself
                invited_player = BookingPlayer(
                    booking_id=new_booking.id,
                    member_id=player_id,
                    status='pending',
                    invited_by=current_user.id
                )
                db.session.add(invited_player)
                invited_count += 1
        
        db.session.commit()
        
        # Audit log the roll-up creation
        audit_log_create('Booking', new_booking.id, 
                        f'Created roll-up booking for {new_booking.booking_date}',
                        {'session': new_booking.session, 'invited_players': invited_count,
                         'organizer': current_user.username})
        
        session_name = current_app.config.get('DAILY_SESSIONS', {}).get(new_booking.session, f'Session {new_booking.session}')
        
        if invited_count > 0:
            flash(f'Roll-up booking created for {new_booking.booking_date.strftime("%B %d, %Y")} - {session_name}. '
                  f'{invited_count} players have been invited and will receive notifications.', 'success')
        else:
            flash(f'Roll-up booking created for {new_booking.booking_date.strftime("%B %d, %Y")} - {session_name}. '
                  f'You can invite more players later if needed.', 'success')
        
        return redirect(url_for('my_games'))
    
    return render_template('book_rollup.html', form=form, title='Book Roll-Up',
                         menu_items=app.config['MENU_ITEMS'],
                         admin_menu_items=app.config['ADMIN_MENU_ITEMS'])


@app.route('/rollup/respond/<int:booking_id>/<action>')
@login_required
def respond_to_rollup(booking_id, action):
    """
    Route: Respond to Roll-Up Invitation
    - Allows players to accept or decline roll-up invitations
    """
    # Validate action
    if action not in ['accept', 'decline']:
        abort(400)
    
    # Find the booking player record
    booking_player = db.session.scalar(
        sa.select(BookingPlayer).where(
            BookingPlayer.booking_id == booking_id,
            BookingPlayer.member_id == current_user.id
        )
    )
    
    if not booking_player:
        flash('Roll-up invitation not found or you were not invited to this roll-up.', 'error')
        return redirect(url_for('my_games'))
    
    if booking_player.status != 'pending':
        flash(f'You have already {booking_player.status} this roll-up invitation.', 'info')
        return redirect(url_for('my_games'))
    
    # Update the response
    new_status = 'confirmed' if action == 'accept' else 'declined'
    booking_player.status = new_status
    booking_player.response_at = datetime.utcnow()
    
    db.session.commit()
    
    # Audit log the response
    audit_log_update('BookingPlayer', booking_player.id,
                    f'Responded to roll-up invitation: {new_status}',
                    {'old_status': 'pending', 'booking_id': booking_id})
    
    booking = booking_player.booking
    organizer_name = booking.organizer.firstname
    session_name = current_app.config.get('DAILY_SESSIONS', {}).get(booking.session, f'Session {booking.session}')
    
    if action == 'accept':
        flash(f'You have accepted the roll-up invitation for {booking.booking_date.strftime("%B %d, %Y")} - {session_name}. '
              f'{organizer_name} will be notified.', 'success')
    else:
        flash(f'You have declined the roll-up invitation for {booking.booking_date.strftime("%B %d, %Y")} - {session_name}. '
              f'{organizer_name} will be notified.', 'info')
    
    return redirect(url_for('my_games'))


@app.route('/rollup/manage/<int:booking_id>')
@login_required
def manage_rollup(booking_id):
    """
    Route: Manage Roll-Up
    - Allows organizers to view and manage their roll-up bookings
    """
    booking = db.session.get(Booking, booking_id)
    
    if not booking or booking.booking_type != 'rollup':
        abort(404)
    
    # Check if current user is the organizer
    if booking.organizer_id != current_user.id:
        audit_log_security_event('ACCESS_DENIED', f'Unauthorized access to roll-up booking {booking_id}')
        abort(403)
    
    # Get all players for this roll-up
    players = db.session.scalars(
        sa.select(BookingPlayer)
        .join(Member, BookingPlayer.member_id == Member.id)
        .where(BookingPlayer.booking_id == booking_id)
        .order_by(BookingPlayer.status.desc(), Member.firstname)
    ).all()
    
    session_name = current_app.config.get('DAILY_SESSIONS', {}).get(booking.session, f'Session {booking.session}')
    
    # Create a simple form for CSRF protection
    csrf_form = FlaskForm()
    
    return render_template('manage_rollup.html', booking=booking, players=players,
                         session_name=session_name, title='Manage Roll-Up',
                         today=date.today(), csrf_form=csrf_form,
                         menu_items=app.config['MENU_ITEMS'],
                         admin_menu_items=app.config['ADMIN_MENU_ITEMS'])


@app.route('/rollup/cancel/<int:booking_id>', methods=['POST'])
@login_required
def cancel_rollup(booking_id):
    """
    Route: Cancel Roll-Up
    - Allows organizers to cancel their roll-up bookings
    """
    booking = db.session.get(Booking, booking_id)
    
    if not booking or booking.booking_type != 'rollup':
        abort(404)
    
    # Check if current user is the organizer
    if booking.organizer_id != current_user.id:
        audit_log_security_event('ACCESS_DENIED', f'Unauthorized cancellation attempt for roll-up booking {booking_id}')
        abort(403)
    
    # Check if booking is in the future
    if booking.booking_date <= date.today():
        flash('Cannot cancel roll-ups for today or past dates.', 'error')
        return redirect(url_for('manage_rollup', booking_id=booking_id))
    
    booking_info = f'{booking.booking_date.strftime("%B %d, %Y")} - Session {booking.session}'
    
    # Delete the booking (cascade will handle booking_players)
    db.session.delete(booking)
    db.session.commit()
    
    # Audit log the cancellation
    audit_log_delete('Booking', booking_id, f'Cancelled roll-up booking: {booking_info}')
    
    flash(f'Roll-up booking for {booking_info} has been cancelled. All invited players will be notified.', 'success')
    return redirect(url_for('my_games'))


@app.route('/rollup/remove_player/<int:booking_id>', methods=['POST'])
@login_required
def remove_rollup_player(booking_id):
    """
    Route: Remove Player from Roll-Up
    - Allows organizers to remove players from their roll-up bookings
    """
    booking = db.session.get(Booking, booking_id)
    
    if not booking or booking.booking_type != 'rollup':
        abort(404)
    
    # Check if current user is the organizer
    if booking.organizer_id != current_user.id:
        audit_log_security_event('ACCESS_DENIED', f'Unauthorized player removal attempt for roll-up booking {booking_id}')
        abort(403)
    
    # Get player ID from form
    player_id = request.form.get('player_id')
    if not player_id:
        flash('Invalid player ID.', 'error')
        return redirect(url_for('manage_rollup', booking_id=booking_id))
    
    # Find the booking player
    booking_player = db.session.scalar(
        sa.select(BookingPlayer)
        .join(Member, BookingPlayer.member_id == Member.id)
        .where(
            BookingPlayer.booking_id == booking_id,
            BookingPlayer.id == player_id
        )
    )
    
    if not booking_player:
        flash('Player not found in this roll-up.', 'error')
        return redirect(url_for('manage_rollup', booking_id=booking_id))
    
    # Don't allow removing the organizer
    if booking_player.member_id == booking.organizer_id:
        flash('Cannot remove the organizer from the roll-up.', 'error')
        return redirect(url_for('manage_rollup', booking_id=booking_id))
    
    player_name = f'{booking_player.member.firstname} {booking_player.member.lastname}'
    
    # Remove the player
    db.session.delete(booking_player)
    db.session.commit()
    
    # Audit log the removal
    audit_log_delete('BookingPlayer', player_id, 
                    f'Removed {player_name} from roll-up booking {booking_id}')
    
    flash(f'{player_name} has been removed from the roll-up.', 'success')
    return redirect(url_for('manage_rollup', booking_id=booking_id))
