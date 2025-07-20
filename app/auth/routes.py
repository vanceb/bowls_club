# Authentication routes for the Bowls Club application
from datetime import datetime, timedelta
from flask import render_template, flash, redirect, url_for, request, current_app
from flask_login import current_user, login_user, logout_user, login_required
from urllib.parse import urlsplit
import sqlalchemy as sa

from app.auth import bp
from app import db
from app.models import Member
from app.forms import LoginForm, RequestResetForm, ResetPasswordForm, PasswordResetForm, EditProfileForm
from app.utils import generate_reset_token, verify_reset_token, send_reset_email
from app.audit import audit_log_authentication, audit_log_update, audit_log_security_event


@bp.route('/login', methods=['GET', 'POST'])
def login():
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
                    return render_template('auth/login.html', form=form)
                
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
        
        return render_template('auth/login.html', form=form)
        
    except Exception as e:
        current_app.logger.error(f"Error in login route: {str(e)}")
        flash('An error occurred during login. Please try again.', 'error')
        return render_template('auth/login.html', form=LoginForm())


@bp.route('/logout')
@login_required
def logout():
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


@bp.route('/reset_password', methods=['GET', 'POST'])
def reset_password_request():
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
                    flash('Password reset instructions have been sent to your email.', 'info')
                else:
                    audit_log_authentication('PASSWORD_RESET_REQUEST', user.username, False)
                    flash('Error sending reset email. Please try again later.', 'error')
            else:
                # Don't reveal whether email exists or not
                audit_log_security_event('PASSWORD_RESET_UNKNOWN_EMAIL', 
                                       f'Password reset request for unknown email: {form.email.data}')
                flash('Password reset instructions have been sent to your email.', 'info')
            
            return redirect(url_for('auth.login'))
        
        return render_template('auth/reset_password_request.html', form=form)
        
    except Exception as e:
        current_app.logger.error(f"Error in reset_password_request route: {str(e)}")
        flash('An error occurred. Please try again.', 'error')
        return render_template('auth/reset_password_request.html', form=RequestResetForm())


@bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
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
            flash('Invalid or expired reset link.', 'error')
            return redirect(url_for('auth.reset_password_request'))
        
        form = ResetPasswordForm()
        
        if form.validate_on_submit():
            # Update password
            user.set_password(form.password.data)
            db.session.commit()
            
            # Audit log
            audit_log_authentication('PASSWORD_RESET', user.username, True)
            
            flash('Your password has been reset successfully. You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        
        return render_template('auth/reset_password.html', form=form)
        
    except Exception as e:
        current_app.logger.error(f"Error in reset_password route: {str(e)}")
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('auth.reset_password_request'))


@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
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
            return redirect(url_for('auth.profile'))
        
        # Pre-populate form with current values
        elif request.method == 'GET':
            form.firstname.data = current_user.firstname
            form.lastname.data = current_user.lastname
            form.email.data = current_user.email
            form.phone.data = current_user.phone
            form.share_email.data = current_user.share_email
            form.share_phone.data = current_user.share_phone
        
        return render_template('auth/edit_profile.html', form=form)
        
    except Exception as e:
        current_app.logger.error(f"Error in profile route: {str(e)}")
        flash('An error occurred while loading your profile.', 'error')
        return render_template('auth/edit_profile.html', form=EditProfileForm(current_user.email))


@bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    """
    Change password for logged-in user
    """
    try:
        form = PasswordResetForm()
        
        if form.validate_on_submit():
            # Verify current password
            if not current_user.check_password(form.current_password.data):
                flash('Current password is incorrect.', 'error')
                return render_template('auth/change_password.html', form=form)
            
            # Update password
            current_user.set_password(form.password.data)
            db.session.commit()
            
            # Audit log
            audit_log_authentication('PASSWORD_CHANGE', current_user.username, True)
            
            flash('Your password has been changed successfully.', 'success')
            return redirect(url_for('auth.profile'))
        
        return render_template('auth/change_password.html', form=form)
        
    except Exception as e:
        current_app.logger.error(f"Error in change_password route: {str(e)}")
        flash('An error occurred while changing your password.', 'error')
        return redirect(url_for('auth.profile'))