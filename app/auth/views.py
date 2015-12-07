from flask import render_template, flash, request, redirect, url_for
from flask.ext.login import login_user, logout_user, login_required, current_user
from . import auth
from .forms import LoginForm, RegistrationForm, ChangePasswordForm, ResetPasswordForm, \
            ForgotPasswordForm, ChangeEmailForm, ChangeUsernameForm
from .. import db
from ..models import User
from ..email import send_email


@auth.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.ping()
        if not current_user.confirmed and \
            request.endpoint[:5] != 'auth.' and \
            request.endpoint != 'static':
                return redirect(url_for('auth.unconfirmed'))

@auth.route('/login', methods = ['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email = form.email.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            return redirect(request.args.get('next') or url_for('main.index'))
        flash("Invaild email or password!")
    return render_template('auth/login.html', form = form)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for('main.index'))

@auth.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email = form.email.data,
                    username = form.username.data,
                    password = form.password.data)
        db.session.add(user)
        db.session.commit()
        token = user.generate_confirmation_token()
        send_email(user.email, 'Confirm Your Account',
                'auth/email/confirm', user = user, token = token)
        flash('A confirmation email has been sent to you by email.')
        return redirect(url_for('main.index'))
    return render_template('auth/register.html', form = form)

@auth.route('/confirm/<token>')
@login_required
def confirm(token):
    if current_user.confirmed:
        return redirect(url_for('main.index'))
    if current_user.confirm(token):
        flash('You have confirmed your account.Thanks!')
    else:
        flash('The confirmation link is invalid or has expired.')
    return redirect(url_for('main.index'))

@auth.route('/unconformed')
def unconfirmed():
    if current_user.is_anonymous or current_user.confirmed:
        return redirect(url_for('main.index'))
    return render_template('auth/unconfirmed.html')

@auth.route('/confirm')
@login_required
def resend_confirmation():
    token = current_user.generate_confirmation_token()
    send_email(current_user.email, 'Confirm Your Account',
                'auth/email/confirm', user = current_user, token = token)
    flash('A new confirmation email has been sent to you by email.')
    return redirect(url_for('main.index'))

@auth.route('/change-password', methods = ['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.old_password.data):
            current_user.password = form.new_password.data
            db.session.add(current_user)
            flash("You have changed your password")
            return redirect(url_for('main.index'))
        else:
            flash("Invalid password")
    return render_template('auth/change_password.html', form = form)

@auth.route('/change-username', methods = ['GET', 'POST'])
@login_required
def change_username():
    form = ChangeUsernameForm()
    if form.validate_on_submit():
        current_user.username = form.new_username.data
        db.session.add(current_user)
        db.session.commit()
        flash("You have changed your username")
        return redirect(url_for('main.index'))
    return render_template('auth/change_username.html', form = form)

@auth.route('/forgot-password', methods = ['GET', 'POST'])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        token = user.generate_reset_password_token()
        send_email(form.email.data, 'Rest Your Password',
                'auth/email/reset', user = user, token = token)
        flash('An email with instructions to reset your password has been sent to you by email.')
        return redirect(url_for('auth.login'))
    return render_template('auth/forgot_password.html', form = form)
    

@auth.route('/reset-password/<token>', methods = ['GET', 'POST'])
def reset_password(token):
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None:
            flash('The user unexits!')
            return render_template('auth/reset_password.html', form = form)
        if user.reset_password(token, form.new_password.data):
            flash('You have reset your password.')
            return redirect(url_for('auth.login'))
        else:
            flash('The reset link is invalid or has expired.')
            return redirect(url_for('main.index'))
    return render_template('auth/reset_password.html', form = form)

@auth.route('/change-email', methods = ['GET', 'POST'])
@login_required
def change_email_request():
    form = ChangeEmailForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.password.data):
            token = current_user.generate_change_email_token(form.new_email.data)
            send_email(form.new_email.data, 'Change Your Email',
                'auth/email/change_email', user = current_user, token = token)
            flash('A confirmation email has been sent to your new email.')
            return redirect(url_for('main.index'))
        else:
            flash("Invalid email or password!")
    return render_template('auth/change_email.html', form = form)

@auth.route('/change-email/<token>')
@login_required
def change_email(token):
    if current_user.change_email(token):
        flash("You have changed your email!")
    else:
        flash("Invalid request")
    return redirect(url_for('main.index'))
