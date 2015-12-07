from flask.ext.wtf import Form
from wtforms import StringField, BooleanField, SubmitField, PasswordField
from wtforms.validators import Required, Length, Email, Regexp, EqualTo
from wtforms import ValidationError
from ..models import User

class LoginForm(Form):
    email = StringField('Email', validators = [Required(), Length(1, 64), Email()])
    password = PasswordField('Password', validators = [Required()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class RegistrationForm(Form):
    email = StringField('Email', validators = [Required(), Length(1, 64), Email()])
    username = StringField('Username', validators = [Required(), Length(1, 64),
                                            Regexp('^[A-za-z][A-Za-z0-9_.]*$', 0,
                                                "Usernames must have only letters, "
                                                "numbers, dots or underscores")])
    password = PasswordField('Password', validators = [Required(), EqualTo('password2',
                                                message = 'Passwords must match')])
    password2 = PasswordField('Confirm Password', validators = [Required()])
    submit = SubmitField('Register')

    def validate_email(self, field):
        if User.query.filter_by(email = field.data).first():
            raise ValidationError('Email already registered.')

    def validate_username(self, field):
        if User.query.filter_by(username = field.data).first():
            raise ValidationError('Username already in use.')

class ChangePasswordForm(Form):
    old_password = PasswordField("Old Password", validators = [Required()])
    new_password = PasswordField("New Password", validators = [
                                    Required(), EqualTo('confirm_password',
                                    message = 'Passwords must match')])
    confirm_password = PasswordField("Confirm New Password", validators = [Required()])
    submit = SubmitField('Change')

class ForgotPasswordForm(Form):
    email = StringField("Your Email", validators = [Required(), Length(1, 64), Email()])
    submit = SubmitField('Submit')

    def validate_email(self, field):
        if User.query.filter_by(email = field.data).first() is None:
            raise ValidationError('User unexit!')

class ResetPasswordForm(Form):
    email = StringField("Your Email", validators = [Required(), Length(1, 64), Email()])
    new_password = PasswordField("New Password", validators = [
                                    Required(), EqualTo('confirm_password',
                                    message = 'Passwords must match')])
    confirm_password = PasswordField("Confirm New Password", validators = [Required()])
    submit = SubmitField('Reset')

class ChangeEmailForm(Form):
    new_email = StringField('New Email', validators = [Required(), Length(1, 64), Email()])
    password = PasswordField('Password', validators=[Required()])
    submit = SubmitField('Change')

    def validate_new_email(self, field):
        if User.query.filter_by(email = field.data).first() is not None:
            raise ValidationError('Email already registered.')

class ChangeUsernameForm(Form):
    new_username = StringField('New Username', validators = [Required(), Length(1, 64),
                                            Regexp('^[A-za-z][A-Za-z0-9_.]*$', 0,
                                                "Usernames must have only letters, "
                                                "numbers, dots or underscores")])
    submit = SubmitField('Change')

    def validate_new_username(self, field):
        if User.query.filter_by(username = field.data).first():
            raise ValidationError('Username already in use.')