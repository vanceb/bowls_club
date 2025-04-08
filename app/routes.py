from flask import render_template, flash, redirect, url_for, request
from app import app, db
from app.forms import LoginForm, MemberForm
from flask_login import current_user, login_user, logout_user, login_required
from urllib.parse import urlsplit
import sqlalchemy as sa
from werkzeug.security import generate_password_hash
from app.models import Member


@app.route("/")
@app.route("/index")
@login_required
def index():
    return render_template('index.html', title='Home', menu_items=app.config['MENU_ITEMS'])


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(Member).where(Member.username == form.username.data))
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
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
            password_hash=generate_password_hash(form.password.data)
        )
        # Add to the database
        db.session.add(new_member)
        db.session.commit()
        flash(f'Joining application submitted for {form.firstname.data} {form.lastname.data}', 'success')
        return redirect(url_for('login'))  # Redirect to the homepage or another page
    if form.errors:
        flash(f'There are errors in your application.  Please review your application and try again.', 'danger')
    return render_template('add_member.html', form=form)