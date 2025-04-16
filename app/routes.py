from flask import render_template, flash, redirect, url_for, request, abort, jsonify
from app import app, db

from app.forms import LoginForm, MemberForm, EditMemberForm, RequestResetForm, ResetPasswordForm
from flask_login import current_user, login_user, logout_user, login_required
from urllib.parse import urlsplit
import sqlalchemy as sa
from werkzeug.security import generate_password_hash
from app.models import Member, Role
from functools import wraps
from app.utils import generate_reset_token, verify_reset_token, send_reset_email

# Create an @admin_required decorator to protect admin routes
# This decorator checks if the current user is authenticated and is an admin
# If not, it aborts the request with a 403 Forbidden status
# This decorator can be used to protect any route that requires admin access
def admin_required(f):
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
    return render_template('index.html', title='Home', menu_items=app.config['MENU_ITEMS'], admin_menu_items=app.config['ADMIN_MENU_ITEMS'])


@app.route('/login', methods=['GET', 'POST'])
def login():
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
    members = db.session.scalars(sa.select(Member).order_by(Member.firstname)).all()
    return render_template('members.html', members=members, menu_items=app.config['MENU_ITEMS'], admin_menu_items=app.config['ADMIN_MENU_ITEMS'])


@app.route('/search_members', methods=['GET'])
@login_required
def search_members():
    query = request.args.get('q', '').strip()
    # Search by first name, last name, or username
    members = Member.query.filter(
        (Member.firstname.ilike(f'%{query}%')) |
        (Member.lastname.ilike(f'%{query}%')) |
        (Member.email.ilike(f'%{query}%'))
    ).all()

    # Return JSON response with all member details, including roles
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
                'roles': [{'id': role.id, 'name': role.name} for role in member.roles]  # Include roles
            }
            for member in members
        ]
    })


@app.route('/admin')
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html', title='Admin Dashboard', menu_items=app.config['MENU_ITEMS'], admin_menu_items=app.config['ADMIN_MENU_ITEMS'])


@app.route('/admin/manage_members', methods=['GET'])
@admin_required
def manage_members():
    members = db.session.scalars(sa.select(Member).order_by(Member.firstname)).all()
    return render_template(
        'manage_members.html',
        title='Manage Members',
        members=members,  # Pass the members list to the template
        menu_items=app.config['MENU_ITEMS'],
        admin_menu_items=app.config['ADMIN_MENU_ITEMS']
    )


@app.route('/admin/edit_member/<int:member_id>', methods=['GET', 'POST'])
@admin_required
def edit_member(member_id):
    member = db.session.get(Member, member_id)
    if not member:
        abort(404)

    form = EditMemberForm(obj=member)
    form.member_id.data = member.id  # Set the member_id field

    # Fetch all roles for the roles section
    roles = db.session.scalars(sa.select(Role).order_by(Role.name)).all()
    form.roles.choices = [(role.id, role.name) for role in roles]  # Populate roles field

    # Pre-select member's roles for GET requests
    if request.method == 'GET':
        form.roles.data = [role.id for role in member.roles]

    # Normalize the submitted data for the roles field
    if request.method == 'POST':
        raw_roles = request.form.getlist('roles')  # Always returns a list
        print("Raw roles field data:", raw_roles)  # Debugging
        form.roles.data = [int(role_id) for role_id in raw_roles]  # Convert to integers

    print("Form data received:", request.form)
    print("Roles field choices:", form.roles.choices)
    print("Roles field data (selected):", form.roles.data)

    if form.validate_on_submit():
        if form.submit_update.data:
            # Update member details
            member.username = form.username.data
            member.firstname = form.firstname.data
            member.lastname = form.lastname.data
            member.email = form.email.data
            member.phone = form.phone.data
            member.is_admin = form.is_admin.data
            member.gender = form.gender.data  # Update gender
            member.status = form.status.data  # Update status

            # Update roles
            selected_role_ids = form.roles.data  # Get selected roles from the form
            print("Selected role IDs:", selected_role_ids)  # Debugging
            selected_roles = db.session.scalars(sa.select(Role).where(Role.id.in_(selected_role_ids))).all()
            member.roles = selected_roles  # Update the member's roles
#DEBUG
            print("Selected role IDs:", selected_role_ids)
            print("Updated member roles:", member.roles)
            print("Form validation status:", form.validate_on_submit())
            print("Form errors:", form.errors)
            print("Raw roles field data:", request.form.getlist('roles'))
            print("Form data attribute:", form.data)
            
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


# Password Reset Routes
@app.route('/reset_password', methods=['GET', 'POST'])
def pw_reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(Member).where(Member.email == form.email.data))
        if user:
            token = generate_reset_token(user.email)
            reset_url = url_for('pw_reset', token=token, _external=True)
            send_reset_email(user.email, reset_url)

        # If the email is not found, we still want to inform the user
        # without revealing whether the email exists in the database
        flash('If that email address is registered, you will receive an email with instructions to reset your password.', 'info')

        return redirect(url_for('login'))
    return render_template('pw_reset_request.html', form=form)


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def pw_reset(token):
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
