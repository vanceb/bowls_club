# Member blueprint routes - consolidates all member-related functionality
# This file contains routes moved from auth, admin, main, and api blueprints

from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_user, logout_user, current_user, login_required
from urllib.parse import urlsplit
import sqlalchemy as sa
from app import db
from app.models import Member, Role, Event, Booking, PoolRegistration
from app.forms import (LoginForm, RequestResetForm, ResetPasswordForm, 
                      PasswordChangeForm, EditProfileForm, MemberForm, 
                      EditMemberForm, ImportUsersForm)
from flask_wtf import FlaskForm
from app.members import bp
from app.members.utils import (generate_reset_token, verify_reset_token, send_reset_email, 
                               filter_admin_menu_by_roles, get_member_data)
from app.audit import (audit_log_create, audit_log_update, audit_log_delete, 
                      audit_log_authentication, audit_log_security_event,
                      audit_log_bulk_operation)

# =============================================================================
# AUTHENTICATION ROUTES (/auth/*)
# =============================================================================

@bp.route('/auth/login', methods=['GET', 'POST'])
def auth_login():
    """
    User login route with rate limiting and security logging
    """
    try:
        # If user is already logged in, redirect to index
        if current_user.is_authenticated:
            return redirect(url_for('main.index'))
        
        form = LoginForm()
        
        if form.validate_on_submit():
            # Find user by username
            user = db.session.scalar(
                sa.select(Member).where(Member.username == form.username.data)
            )
            
            # Check if user exists and password is correct
            if user and user.check_password(form.password.data):
                # Check if account is locked
                if user.lockout:
                    audit_log_security_event('LOGIN_ATTEMPT_LOCKED_ACCOUNT', 
                                           f'Login attempt on locked account: {user.username}')
                    flash('Your account has been locked. Please contact the administrator.', 'error')
                    return render_template('member_login.html', form=form)
                
                # Successful login
                login_user(user, remember=form.remember_me.data)
                
                # Update last login time
                user.last_login = datetime.utcnow()
                db.session.commit()
                
                # Audit log successful login
                audit_log_authentication('LOGIN', user.username, True)
                
                # Redirect to originally requested page or index
                next_page = request.args.get('next')
                if not next_page or urlsplit(next_page).netloc != '':
                    next_page = url_for('main.index')
                
                flash(f'Welcome back, {user.firstname}!', 'success')
                return redirect(next_page)
            else:
                # Failed login attempt
                attempted_username = form.username.data
                audit_log_authentication('LOGIN', attempted_username, False)
                flash('Invalid username or password', 'error')
        
        return render_template('member_login.html', form=form)
        
    except Exception as e:
        current_app.logger.error(f"Error in login route: {str(e)}")
        flash('An error occurred during login. Please try again.', 'error')
        return render_template('member_login.html', form=LoginForm())


@bp.route('/auth/logout')
@login_required
def auth_logout():
    """
    User logout route with audit logging
    """
    try:
        # Log the logout event
        audit_log_authentication('LOGOUT', current_user.username, True)
        
        # Logout user
        logout_user()
        
        flash('You have been logged out successfully.', 'info')
        return redirect(url_for('main.index'))
        
    except Exception as e:
        current_app.logger.error(f"Error in logout route: {str(e)}")
        flash('An error occurred during logout.', 'error')
        return redirect(url_for('main.index'))


@bp.route('/auth/reset_password', methods=['GET', 'POST'])
def auth_reset_password_request():
    """
    Request password reset - send email with reset link
    """
    try:
        # If user is already logged in, redirect to index
        if current_user.is_authenticated:
            return redirect(url_for('main.index'))
        
        form = RequestResetForm()
        
        if form.validate_on_submit():
            # Find user by email
            user = db.session.scalar(
                sa.select(Member).where(Member.email == form.email.data)
            )
            
            if user:
                # Generate reset token
                token = generate_reset_token(user)
                
                # Send reset email
                if send_reset_email(user, token):
                    audit_log_authentication('PASSWORD_RESET_REQUEST', user.username, True)
                else:
                    audit_log_authentication('PASSWORD_RESET_REQUEST', user.username, False, 
                                           {'error': 'Failed to send reset email'})
            else:
                # Security: Don't reveal whether email exists or not - same response
                audit_log_security_event('PASSWORD_RESET_UNKNOWN_EMAIL', 
                                       f'Password reset request for unknown email: {form.email.data}')
            
            # Always show the same message regardless of email validity (email enumeration protection)
            flash('If that email address is in our system, you will receive password reset instructions shortly.', 'info')
            
            return redirect(url_for('members.auth_login'))
        
        return render_template('member_password_reset_request.html', form=form)
        
    except Exception as e:
        current_app.logger.error(f"Error in reset_password_request route: {str(e)}")
        flash('An error occurred. Please try again.', 'error')
        return render_template('member_password_reset_request.html', form=RequestResetForm())


@bp.route('/auth/reset_password/<token>', methods=['GET', 'POST'])
def auth_reset_password(token):
    """
    Reset password with valid token
    """
    try:
        # If user is already logged in, redirect to index
        if current_user.is_authenticated:
            return redirect(url_for('main.index'))
        
        # Verify token
        user = verify_reset_token(token)
        if not user:
            # Audit log invalid/expired token attempt
            audit_log_security_event('PASSWORD_RESET_INVALID_TOKEN', 
                                   f'Invalid or expired reset token used', 
                                   {'token_prefix': token[:8] + '...' if len(token) >= 8 else token})
            flash('Invalid or expired reset link. Please request a new password reset.', 'error')
            return redirect(url_for('members.auth_reset_password_request'))
        
        form = ResetPasswordForm()
        
        if form.validate_on_submit():
            # Update password
            user.set_password(form.password.data)
            db.session.commit()
            
            # Audit log password reset completion
            audit_log_authentication('PASSWORD_RESET', user.username, True, 
                                   {'method': 'email_token', 'user_id': user.id})
            
            flash('Your password has been reset successfully. You can now log in.', 'success')
            return redirect(url_for('members.auth_login'))
        
        return render_template('member_password_reset.html', form=form)
        
    except Exception as e:
        current_app.logger.error(f"Error in reset_password route: {str(e)}")
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('members.auth_reset_password_request'))


@bp.route('/auth/profile', methods=['GET', 'POST'])
@login_required
def auth_profile():
    """
    User profile page - view and edit profile information
    """
    try:
        form = EditProfileForm(current_user.email)
        
        if form.validate_on_submit():
            # Update profile information
            current_user.firstname = form.firstname.data
            current_user.lastname = form.lastname.data
            current_user.email = form.email.data
            current_user.phone = form.phone.data
            current_user.share_email = form.share_email.data
            current_user.share_phone = form.share_phone.data
            
            db.session.commit()
            
            # Audit log
            audit_log_update('Member', current_user.id, 
                           f'Updated profile information for {current_user.username}')
            
            flash('Your profile has been updated successfully.', 'success')
            return redirect(url_for('members.auth_profile'))
        
        # Pre-populate form with current values
        elif request.method == 'GET':
            form.firstname.data = current_user.firstname
            form.lastname.data = current_user.lastname
            form.email.data = current_user.email
            form.phone.data = current_user.phone
            form.share_email.data = current_user.share_email
            form.share_phone.data = current_user.share_phone
        
        return render_template('member_profile_edit.html', form=form)
        
    except Exception as e:
        current_app.logger.error(f"Error in profile route: {str(e)}")
        flash('An error occurred while loading your profile.', 'error')
        return render_template('member_profile_edit.html', form=EditProfileForm(current_user.email))


@bp.route('/auth/change_password', methods=['GET', 'POST'])
@login_required
def auth_change_password():
    """
    Change password for logged-in user
    """
    try:
        form = PasswordChangeForm()
        
        if form.validate_on_submit():
            # Verify current password
            if not current_user.check_password(form.current_password.data):
                flash('Current password is incorrect.', 'error')
                return render_template('member_password_change.html', form=form)
            
            # Update password
            current_user.set_password(form.password.data)
            db.session.commit()
            
            # Audit log
            audit_log_authentication('PASSWORD_CHANGE', current_user.username, True)
            
            flash('Your password has been changed successfully.', 'success')
            return redirect(url_for('members.auth_profile'))
        
        return render_template('member_password_change.html', form=form)
        
    except Exception as e:
        current_app.logger.error(f"Error in change_password route: {str(e)}")
        flash('An error occurred while changing your password.', 'error')
        return redirect(url_for('members.auth_profile'))


# =============================================================================
# ADMIN ROUTES (/admin/*)
# =============================================================================

def admin_required(f):
    """Decorator to require admin privileges"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Access denied. Administrator privileges required.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*required_roles):
    """Decorator to require specific roles"""
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'error')
                return redirect(url_for('members.auth_login'))
            
            # Admin users have access to everything
            if current_user.is_admin:
                return f(*args, **kwargs)
            
            # Check if user has any of the required roles
            user_roles = [role.name for role in current_user.roles]
            if not any(role in user_roles for role in required_roles):
                flash('Access denied. You do not have the required permissions.', 'error')
                return redirect(url_for('main.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@bp.route('/admin/manage_members')
@login_required
@role_required('User Manager')
def admin_manage_members():
    """
    Admin interface for managing members
    """
    try:
        # Get all members ordered by lastname, firstname
        members = db.session.scalars(
            sa.select(Member).order_by(Member.lastname, Member.firstname)
        ).all()
        
        return render_template('member_admin_manage.html', members=members)
        
    except Exception as e:
        current_app.logger.error(f"Error in manage_members route: {str(e)}")
        flash('An error occurred while loading the members list.', 'error')
        return redirect(url_for('main.index'))


@bp.route('/admin/edit_member/<int:member_id>', methods=['GET', 'POST'])
@login_required
@role_required('User Manager')
def admin_edit_member(member_id):
    """
    Admin interface for editing or deleting a member
    """
    try:
        member = db.session.get(Member, member_id)
        if not member:
            flash('Member not found.', 'error')
            return redirect(url_for('members.admin_manage_members'))
        
        form = EditMemberForm(obj=member)
        
        # Handle member deletion
        if request.method == 'POST' and 'delete_member' in request.form:
            member_name = f"{member.firstname} {member.lastname}"
            
            db.session.delete(member)
            db.session.commit()
            
            # Audit log
            audit_log_delete('Member', member_id, f'Deleted member: {member_name}')
            
            flash(f'Member {member_name} has been deleted successfully.', 'success')
            return redirect(url_for('members.admin_manage_members'))
        
        # Handle member update
        if form.validate_on_submit():
            # Update member information
            member.firstname = form.firstname.data
            member.lastname = form.lastname.data
            member.email = form.email.data
            member.phone = form.phone.data
            member.username = form.username.data
            member.status = form.status.data
            member.share_email = form.share_email.data
            member.share_phone = form.share_phone.data
            member.lockout = form.lockout.data
            member.is_admin = form.is_admin.data
            
            db.session.commit()
            
            # Audit log
            audit_log_update('Member', member.id, 
                           f'Updated member: {member.firstname} {member.lastname}')
            
            flash('Member updated successfully.', 'success')
            return redirect(url_for('members.admin_manage_members'))
        
        return render_template('member_admin_edit.html', form=form, member=member)
        
    except Exception as e:
        current_app.logger.error(f"Error in edit_member route: {str(e)}")
        flash('An error occurred while editing the member.', 'error')
        return redirect(url_for('members.admin_manage_members'))


@bp.route('/admin/reset_member_password/<int:member_id>', methods=['GET', 'POST'])
@login_required
@role_required('User Manager')
def admin_reset_member_password(member_id):
    """
    Admin interface for resetting a member's password
    """
    try:
        member = db.session.get(Member, member_id)
        if not member:
            flash('Member not found.', 'error')
            return redirect(url_for('members.admin_manage_members'))
        
        form = ResetPasswordForm()
        
        if form.validate_on_submit():
            # Update password
            member.set_password(form.password.data)
            db.session.commit()
            
            # Audit log
            audit_log_authentication('ADMIN_PASSWORD_RESET', member.username, True, 
                                   {'admin_user': current_user.username, 'admin_id': current_user.id})
            
            flash(f'Password reset successfully for {member.firstname} {member.lastname}.', 'success')
            return redirect(url_for('members.admin_manage_members'))
        
        return render_template('member_admin_password_reset.html', form=form, member=member)
        
    except Exception as e:
        current_app.logger.error(f"Error in admin_reset_password route: {str(e)}")
        flash('An error occurred while resetting the password.', 'error')
        return redirect(url_for('members.admin_manage_members'))


@bp.route('/admin/import_users', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_import_users():
    """
    Admin interface for importing users from CSV
    """
    try:
        form = ImportUsersForm()
        
        if form.validate_on_submit():
            import csv
            from io import StringIO
            
            # Read CSV file data
            csv_file = form.csv_file.data
            csv_data = csv_file.read().decode('utf-8')
            csv_reader = csv.DictReader(StringIO(csv_data))
            
            imported_count = 0
            errors = []
            
            # Process each row
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 for Excel row numbering
                try:
                    # Required fields
                    firstname = row.get('firstname', '').strip()
                    lastname = row.get('lastname', '').strip()
                    email = row.get('email', '').strip()
                    phone = row.get('phone', '').strip()
                    
                    # Optional fields
                    username = row.get('username', '').strip()
                    gender = row.get('gender', '').strip()
                    
                    # Validate required fields
                    if not all([firstname, lastname, email, phone]):
                        errors.append(f"Row {row_num}: Missing required fields")
                        continue
                    
                    # Generate username if not provided
                    if not username:
                        username = f"{firstname.lower()}.{lastname.lower()}"
                    
                    # Check if user already exists
                    existing_user = db.session.scalar(
                        sa.select(Member).where(
                            sa.or_(Member.email == email, Member.username == username)
                        )
                    )
                    
                    if existing_user:
                        errors.append(f"Row {row_num}: User with email {email} or username {username} already exists")
                        continue
                    
                    # Create new member with 'Pending' status
                    new_member = Member(
                        firstname=firstname,
                        lastname=lastname,
                        email=email,
                        phone=phone,
                        username=username,
                        gender=gender if gender else None,
                        status='Pending'
                    )
                    
                    # Set a default password (should be reset by admin)
                    new_member.set_password('bowls123')
                    
                    db.session.add(new_member)
                    imported_count += 1
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    continue
            
            # Commit all changes
            if imported_count > 0:
                db.session.commit()
                
                # Audit log bulk operation
                audit_log_bulk_operation('BULK_CREATE', 'Member', imported_count, 
                                       f'Imported {imported_count} members via CSV')
            
            # Show results
            if imported_count > 0:
                flash(f'Successfully imported {imported_count} members.', 'success')
            
            if errors:
                error_msg = f'{len(errors)} errors occurred:\n' + '\n'.join(errors[:10])
                if len(errors) > 10:
                    error_msg += f'\n... and {len(errors) - 10} more errors'
                flash(error_msg, 'error')
            
            if imported_count > 0:
                return redirect(url_for('members.admin_manage_members'))
        
        return render_template('member_admin_import.html', form=form)
        
    except Exception as e:
        current_app.logger.error(f"Error in import_users route: {str(e)}")
        flash('An error occurred during import.', 'error')
        return render_template('member_admin_import.html', form=ImportUsersForm())


@bp.route('/admin/manage_roles', methods=['GET', 'POST'])
@login_required
@role_required('User Manager')
def admin_manage_roles():
    """
    Admin interface for managing roles
    """
    try:
        form = FlaskForm()
        
        if form.validate_on_submit():
            action = request.form.get('action')
            
            if action == 'create_role':
                # Create new role
                role_name = request.form.get('role_name', '').strip()
                
                # Check if role already exists
                existing_role = db.session.scalar(
                    sa.select(Role).where(Role.name == role_name)
                )
                
                if existing_role:
                    flash(f'Role "{role_name}" already exists.', 'error')
                else:
                    new_role = Role(name=role_name)
                    db.session.add(new_role)
                    db.session.commit()
                    
                    # Audit log
                    audit_log_create('Role', new_role.id, f'Created role: {role_name}')
                    
                    flash(f'Role "{role_name}" created successfully.', 'success')
            
            elif action == 'rename':
                # Rename existing role
                role_id = request.form.get('role_id')
                new_name = request.form.get('role_name', '').strip()
                
                role = db.session.get(Role, role_id)
                if role:
                    # Check if role is protected
                    core_roles = current_app.config.get('CORE_ROLES', [])
                    if role.name in core_roles:
                        flash(f'Cannot rename core role "{role.name}". Core roles are protected.', 'error')
                    else:
                        old_name = role.name
                        role.name = new_name
                        db.session.commit()
                        
                        # Audit log
                        audit_log_update('Role', role.id, f'Renamed role from "{old_name}" to "{new_name}"')
                        
                        flash(f'Role renamed from "{old_name}" to "{new_name}".', 'success')
                else:
                    flash(f'Role not found.', 'error')
            
            elif action == 'delete':
                # Delete role
                role_id = request.form.get('role_id')
                
                role = db.session.get(Role, role_id)
                if role:
                    # Check if role is protected
                    core_roles = current_app.config.get('CORE_ROLES', [])
                    if role.name in core_roles:
                        flash(f'Cannot delete core role "{role.name}". Core roles are protected.', 'error')
                    else:
                        role_name = role.name
                        db.session.delete(role)
                        db.session.commit()
                        
                        # Audit log
                        audit_log_delete('Role', role_id, f'Deleted role: {role_name}')
                        
                        flash(f'Role "{role_name}" deleted successfully.', 'success')
                else:
                    flash(f'Role not found.', 'error')
            
            return redirect(url_for('members.admin_manage_roles'))
        
        # Get all roles and users
        roles = db.session.scalars(sa.select(Role).order_by(Role.name)).all()
        users = db.session.scalars(
            sa.select(Member).order_by(Member.lastname, Member.firstname)
        ).all()
        
        # Get core roles from config
        core_roles = current_app.config.get('CORE_ROLES', [])
        
        return render_template('member_admin_roles.html', csrf_form=form, roles=roles, users=users, core_roles=core_roles)
        
    except Exception as e:
        current_app.logger.error(f"Error in manage_roles route: {str(e)}")
        flash('An error occurred while managing roles.', 'error')
        return redirect(url_for('main.index'))


@bp.route('/admin/add_user_to_role', methods=['POST'])
@login_required
@role_required('User Manager')
def admin_add_user_to_role():
    """
    AJAX endpoint for adding a user to a role
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No JSON data provided'}), 400
            
        user_id = data.get('user_id')
        role_id = data.get('role_id')
        
        if not user_id or not role_id:
            return jsonify({'success': False, 'message': 'Missing user_id or role_id'}), 400
        
        user = db.session.get(Member, user_id)
        role = db.session.get(Role, role_id)
        
        if not user or not role:
            return jsonify({'success': False, 'message': 'User or role not found'})
        
        # Check if user already has this role
        if role in user.roles:
            return jsonify({'success': False, 'message': f'{user.firstname} {user.lastname} already has the {role.name} role'})
        
        # Add role to user
        user.roles.append(role)
        db.session.commit()
        
        # Audit log
        audit_log_update('Member', user.id, 
                       f'Added role "{role.name}" to {user.firstname} {user.lastname}')
        
        return jsonify({'success': True, 'message': f'Added {role.name} role to {user.firstname} {user.lastname}'})
        
    except Exception as e:
        current_app.logger.error(f"Error in add_user_to_role route: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred'})


@bp.route('/admin/remove_user_from_role', methods=['POST'])
@login_required
@role_required('User Manager')
def admin_remove_user_from_role():
    """
    AJAX endpoint for removing a user from a role
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No JSON data provided'}), 400
            
        user_id = data.get('user_id')
        role_id = data.get('role_id')
        
        if not user_id or not role_id:
            return jsonify({'success': False, 'message': 'Missing user_id or role_id'}), 400
        
        user = db.session.get(Member, user_id)
        role = db.session.get(Role, role_id)
        
        if not user or not role:
            return jsonify({'success': False, 'message': 'User or role not found'})
        
        # Check if user has this role
        if role not in user.roles:
            return jsonify({'success': False, 'message': f'{user.firstname} {user.lastname} does not have the {role.name} role'})
        
        # Remove role from user
        user.roles.remove(role)
        db.session.commit()
        
        # Audit log
        audit_log_update('Member', user.id, 
                       f'Removed role "{role.name}" from {user.firstname} {user.lastname}')
        
        return jsonify({'success': True, 'message': f'Removed {role.name} role from {user.firstname} {user.lastname}'})
        
    except Exception as e:
        current_app.logger.error(f"Error in remove_user_from_role route: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred'})


# =============================================================================
# MEMBER DIRECTORY AND APPLICATION ROUTES (root level)
# =============================================================================

@bp.route('/directory')
@login_required
def directory():
    """
    Display paginated list of active members
    """
    try:
        from flask_paginate import Pagination, get_page_parameter
        
        # Get page parameter
        page = request.args.get(get_page_parameter(), type=int, default=1)
        per_page = 20
        
        # Get active members (Full, Social, Life)
        members_query = sa.select(Member).where(
            Member.status.in_(['Full', 'Social', 'Life'])
        ).order_by(Member.lastname, Member.firstname)
        
        # Get total count for pagination
        total = db.session.scalar(sa.select(sa.func.count()).select_from(members_query.subquery()))
        
        # Get paginated members
        members = db.session.scalars(
            members_query.offset((page - 1) * per_page).limit(per_page)
        ).all()
        
        # Create pagination object
        pagination = Pagination(page=page, per_page=per_page, total=total,
                               css_framework='bulma')
        
        return render_template('member_directory.html', 
                             members=members, 
                             pagination=pagination,
                             total=total)
    except Exception as e:
        current_app.logger.error(f"Error in members directory route: {str(e)}")
        flash('An error occurred while loading the members directory.', 'error')
        return render_template('member_directory.html', members=[], pagination=None, total=0)


@bp.route('/apply', methods=['GET', 'POST'])
def apply():
    """
    Public member application form for prospective members
    No login required - creates members with 'Pending' status
    """
    try:
        form = MemberForm()
        
        if form.validate_on_submit():
            # Create new member with 'Pending' status
            member = Member(
                username=form.username.data,
                firstname=form.firstname.data,
                lastname=form.lastname.data,
                email=form.email.data,
                phone=form.phone.data,
                share_email=form.share_email.data,
                share_phone=form.share_phone.data,
                status='Pending'  # Always pending for public applications
            )
            
            # Set password if provided
            if form.password.data:
                member.set_password(form.password.data)
            
            db.session.add(member)
            db.session.commit()
            
            # Audit log
            audit_log_create('Member', member.id, 
                           f'Member application submitted: {member.firstname} {member.lastname} ({member.username})',
                           {'status': 'Pending', 'application_type': 'public'})
            
            flash(f'Thank you for your application, {member.firstname}! Your application has been submitted and will be reviewed by our administrators.', 'success')
            return redirect(url_for('main.index'))
        
        return render_template('member_apply.html', form=form)
        
    except Exception as e:
        current_app.logger.error(f"Error in member application route: {str(e)}")
        flash('An error occurred while submitting your application. Please try again.', 'error')
        return render_template('member_apply.html', form=MemberForm())


# =============================================================================
# API ROUTES (/api/v1/*)
# =============================================================================

@bp.route('/api/v1/search', methods=['GET'])
@login_required
def api_search_members():
    """
    Search for members by name (AJAX endpoint)
    Returns different data based on user permissions and route context
    """
    try:
        search_term = request.args.get('q', '').strip()
        route_context = request.args.get('route', 'members')  # 'members' or 'manage_members'
        
        # Determine if user should see admin data and if pending members should be included
        show_admin_data = current_user.is_authenticated and current_user.is_admin
        include_pending = route_context == 'manage_members' and show_admin_data
        
        if not search_term:
            # Return all members based on route context and permissions
            if include_pending:
                # Manage Members route: show ALL members including pending
                members = db.session.scalars(sa.select(Member).order_by(Member.lastname, Member.firstname)).all()
            else:
                # Members route: show only active members
                members = db.session.scalars(
                    sa.select(Member)
                    .where(Member.status.in_(['Full', 'Social', 'Life']))
                    .order_by(Member.lastname, Member.firstname)
                ).all()
        else:
            # Search members based on route context
            if include_pending:
                # Manage Members route: search ALL members including pending
                members = db.session.scalars(sa.select(Member).where(sa.or_(
                    Member.username.ilike(f'%{search_term}%'),
                    Member.firstname.ilike(f'%{search_term}%'),
                    Member.lastname.ilike(f'%{search_term}%'),
                    Member.email.ilike(f'%{search_term}%')
                )).order_by(Member.lastname, Member.firstname)).all()
            else:
                # Members route: search only active members
                members = db.session.scalars(sa.select(Member).where(sa.and_(
                    Member.status.in_(['Full', 'Social', 'Life']),
                    sa.or_(
                        Member.username.ilike(f'%{search_term}%'),
                        Member.firstname.ilike(f'%{search_term}%'),
                        Member.lastname.ilike(f'%{search_term}%'),
                        Member.email.ilike(f'%{search_term}%')
                    )
                )).order_by(Member.lastname, Member.firstname)).all()
                
                # Limit results for non-admin users on Members route
                if not show_admin_data:
                    members = members[:20]
        
        # Format results based on user permissions
        results = []
        for member in members:
            if show_admin_data:
                # Admin users get full data
                member_data = get_member_data(member, show_private_data=True)
                
                # Add admin-specific fields
                member_data.update({
                    'last_seen': member.last_seen.strftime('%Y-%m-%d') if member.last_seen else 'Never',
                    'roles': [{'name': role.name} for role in member.roles] if member.roles else []
                })
            else:
                # Regular users get privacy-filtered data
                member_data = get_member_data(member, show_private_data=False)
            
            results.append(member_data)
        
        return jsonify({
            'success': True,
            'members': results,
            'count': len(results)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in search_members API: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while searching for members'
        }), 500


@bp.route('/api/v1/users_with_roles', methods=['GET'])
@login_required
@admin_required
def api_users_with_roles():
    """
    Get all users with their assigned roles (AJAX endpoint)
    Admin only access
    """
    try:
        # Get all users who have roles assigned
        users_with_roles = db.session.scalars(
            sa.select(Member)
            .join(Member.roles)
            .order_by(Member.lastname, Member.firstname)
            .distinct()
        ).all()
        
        # Format results
        results = []
        for user in users_with_roles:
            user_data = {
                'id': user.id,
                'firstname': user.firstname,
                'lastname': user.lastname,
                'email': user.email,
                'roles': [{'id': role.id, 'name': role.name} for role in user.roles]
            }
            results.append(user_data)
        
        return jsonify({
            'success': True,
            'users': results,
            'count': len(results)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in users_with_roles API: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while retrieving users with roles'
        }), 500