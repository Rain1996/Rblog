import hashlib
import bleach
from . import db, login_manager
from app.exceptions import ValidationError
from flask import current_app, request, url_for
from flask.ext.login import UserMixin, AnonymousUserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from datetime import datetime
from markdown import markdown


class Permission(object):
    FOLLOW = 0x001  
    COMMENT = 0x002
    DELETE_COMMENT = 0x004
    WRITE_ARTICLES = 0x008
    DELETE_ARTICLES = 0x010
    MODERATE = 0x020        #moderate articles and comments
    ADMINISTER = 0x800

class Follow(db.Model):
    __tablenmae__ = 'follows'
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'),
                            primary_key = True)
    followed_id = db.Column(db.Integer, db.ForeignKey('users.id'),
                            primary_key = True)
    timestamp = db.Column(db.DateTime, default = datetime.utcnow)

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key = True)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index = True, default = datetime.utcnow)
    disabled = db.Column(db.Boolean)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'))
    
    def to_json(self):
        json_comment = {
            'url': url_for('api.get_comment', id = self.id, _external = True),
            'post': url_for('api.get_post', id = self.post_id, _external = True),
            'body': self.body,
            'body_html': self.timestamp,
            'author': url_for('api.get_user', id = self.author_id, _external = True),
        }
        return json_comment

    @staticmethod
    def form_json(json_comment):
        body = json_comment.get('body')
        if body is None or body == '':
            raise ValidationError('comment does not have a body')
        return Comment(body = body)

    # create virtual comments
    @staticmethod
    def generate_fake(count = 100):
        from random import seed, randint
        import forgery_py

        seed()
        user_count = User.query.count()
        post_count = Post.query.count()
        for i in range(count):
            u = User.query.offset(randint(0, user_count - 1)).first()
            p = Post.query.offset(randint(0, post_count - 1)).first()
            c = Comment(body = forgery_py.lorem_ipsum.sentences(randint(1, 3)),
                     timestamp = forgery_py.date.date(True), author = u, post = p)
            db.session.add(c)
            db.session.commit()
    
    @staticmethod
    def on_changed_body(target, value, oldvalue, initiator):
        allowed_tags = ['a', 'abbr', 'acronym', 'b', 'code', 'em', 'i', 'strong']
        target.body_html = bleach.linkify(bleach.clean(markdown(value, output_format = 'html'),
                                          tags = allowed_tags, strip = True))

db.event.listen(Comment.body, 'set', Comment.on_changed_body)


class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key = True)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    disabled = db.Column(db.Boolean)
    timestamp = db.Column(db.DateTime, index = True, default = datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    comments = db.relationship('Comment', backref = 'post', lazy = 'dynamic')
    
    def to_json(self):
        json_post = {
            'url': url_for('api.get_post', id = self.id, _external = True),
            'body': self.body,
            'body_html': self.body_html,
            'timestamp': self.timestamp,
            'author': url_for('api.get_user', id = self.author_id, _external = True),
            'comments': url_for('api.get_post_comments', id = self.id, _external = True),
            'comemnt_count': self.comments.count()
        }
        return json_post

    @staticmethod
    def from_json(json_post):
        body = json_post.get('body')
        if body is None or body == '':
            raise ValidationError('post does not have a body')
        return Post(body = body)

    # create virtual posts
    @staticmethod
    def generate_fake(count = 100):
        from random import seed, randint
        import forgery_py

        seed()
        user_count = User.query.count()
        for i in range(count):
            u = User.query.offset(randint(0, user_count - 1)).first()
            p = Post(body = forgery_py.lorem_ipsum.sentences(randint(1, 3)),
                     timestamp = forgery_py.date.date(True), author = u)
            db.session.add(p)
            db.session.commit()

    @staticmethod
    def on_changed_body(target, value, oldvalue, initiator):
        allowed_tags = ['a', 'abbr', 'acronym', 'b', 'blockquote', 'code', 'em', 'i',
                        'li', 'ol', 'pre', 'strong', 'ul', 'h1', 'h2', 'h3', 'p']
        target.body_html = bleach.linkify(bleach.clean(markdown(value, output_format = 'html'),
                                          tags = allowed_tags, strip = True))

db.event.listen(Post.body, 'set', Post.on_changed_body)

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(64), unique = True)
    default = db.Column(db.Boolean, default = False, index = True)
    permissions = db.Column(db.Integer)
    users = db.relationship('User', backref = 'role', lazy = 'dynamic')

    def __repr__(self):
        return '<Role %r>' % self.name

    @staticmethod
    def insert_roles():
        roles = {
            'User': (Permission.FOLLOW |
                     Permission.COMMENT |
                     Permission.DELETE_COMMENT |
                     Permission.WRITE_ARTICLES |
                     Permission.DELETE_ARTICLES, True),
            'Moderator': (Permission.FOLLOW |
                          Permission.COMMENT |
                          Permission.DELETE_COMMENT |
                          Permission.WRITE_ARTICLES |
                          Permission.DELETE_ARTICLES|
                          Permission.MODERATE, False), 
            'Administrator': (0xfff, False)
        }
        for r in roles:
            role = Role.query.filter_by(name = r).first()
            if role is None:
                role = Role(name = r)
                role.permissions = roles[r][0]
                role.default = roles[r][1]
                db.session.add(role)
        db.session.commit()


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(64), unique = True, index = True)
    email = db.Column(db.String(64), unique = True, index = True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    password_hash = db.Column(db.String(128))
    confirmed = db.Column(db.Boolean, default = False)
    name = db.Column(db.String(64))
    location = db.Column(db.String(64))
    about_me = db.Column(db.Text())
    member_since = db.Column(db.DateTime(), default = datetime.utcnow)
    last_seen = db.Column(db.DateTime(), default = datetime.utcnow)
    avatar_hash = db.Column(db.String(32))
    posts = db.relationship('Post', backref = 'author', lazy = 'dynamic')
    comments = db.relationship('Comment', backref = 'author', lazy = 'dynamic')
    followed = db.relationship('Follow',
                                foreign_keys = [Follow.follower_id],
                                backref = db.backref('follower', lazy = 'joined'),
                                lazy = 'dynamic',
                                cascade = 'all, delete-orphan')
    followers = db.relationship('Follow',
                                foreign_keys = [Follow.followed_id],
                                backref = db.backref('followed', lazy = 'joined'),
                                lazy = 'dynamic',
                                cascade = 'all, delete-orphan')

    
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if self.role is None:
            if self.email == current_app.config.get('RBLOG_ADMIN'):
                self.role = Role.query.filter_by(permissions = 0xfff).first()
            if self.role is None:
                self.role = Role.query.filter_by(default = True).first()
       
        if self.email is not None and self.avatar_hash is None:
            self.avatar_hash = hashlib.md5(
                self.email.encode('utf-8')).hexdigest()
        self.followed.append(Follow(followed = self))

    def __repr__(self):
        return '<User %r>' % self.username

    @property
    def password(self):
        raise AttributeError('Password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    # confirm
    def generate_confirmation_token(self, expiration = 3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'confirm': self.id})

    def confirm(self, token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('confirm') != self.id:
            return False
        self.confirmed = True
        db.session.add(self)
        return True
    
    # reset password
    def generate_reset_password_token(self, expiration = 1800):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'reset': self.id})

    def reset_password(self, token, new_password):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('reset') != self.id:
            return False
        self.password = new_password
        db.session.add(self)
        return True

    # change email
    def generate_change_email_token(self, new_email, expiration = 1800):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'change_email': self.id, 'new_email': new_email})

    def change_email(self, token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('change_email') != self.id:
            return False
        new_email = data.get('new_email')
        if new_email is None:
            return False
        self.email = new_email
        self.avatar_hash = hashlib.md5(
            self.email.encode('utf-8')).hexdigest()
        db.session.add(self)
        return True

    def can(self, permissions):
        return self.role is not None and \
            (self.role.permissions & permissions) == permissions
    
    def is_administrator(self):
        return self.can(Permission.ADMINISTER)

    # flash member last seen
    def ping(self):
        self.last_seen = datetime.utcnow()
        db.session.add(self)

    # create Gravatar URL
    def gravatar(self, size = 100, default = 'identicon', rating = 'g'):
        if request.is_secure:
            url = 'https://secure.gravatar.com/avatar'
        else:
            url = 'https://secure.gravatar.com/avatar'
        # I can't open the 'http://www.gravatar.com/avatar'
        # so I use 'https://secure.gravatar.com/avatar' only
        hash = self.avatar_hash or hashlib.md5(self.email.encode('utf-8')).hexdigest()
        return '{url}/{hash}?s={size}&d={default}&r={rating}'.format(
            url = url, hash = hash, size = size, default = default, rating = rating)
    
    # 
    def follow(self, user):
        if not self.is_following(user):
            f = Follow(follower = self, followed = user)
            db.session.add(f)

    def unfollow(self, user):
        f = self.followed.filter_by(followed_id = user.id).first()
        if f:
            db.session.delete(f)

    def is_following(self, user):
        return self.followed.filter_by(followed_id = user.id).first() is not None
    
    def is_followed_by(self, user):
        return self.followers.filter_by(follower_id = user.id).first() is not None


    @property
    def followed_posts(self):
        return Post.query.join(Follow, Follow.followed_id == Post.author_id)\
                            .filter(Follow.follower_id == self.id)

    def to_json(self):
        json_user = {
            'url': url_for('api.get_user', id = self.id, _external = True),
            'username': self.username,
            'member_since': self.member_since,
            'last_seen': self.last_seen,
            'posts': url_for('api.get_user_posts', id = self.id, _external = True),
            'followed_posts': url_for('api.get_user_followed_posts', id = self.id, _external = True),
            'post_count': self.posts.count()
        }
        return json_user

    def generate_auth_token(self, expiration):
        s = Serializer(current_app.config['SECRET_KEY'],
                       expires_in = expiration)
        return s.dumps({'id': self.id}).decode('ascii')

    @staticmethod
    def verify_auth_token(token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return None
        return User.query.get(data['id'])

    # create virtual users
    @staticmethod
    def generate_fake(count = 100):
        from sqlalchemy.exc import IntegrityError
        from random import seed
        import forgery_py

        seed()
        for i in range(count):
            u = User(email = forgery_py.internet.email_address(),
                     username = forgery_py.internet.user_name(True),
                     password = forgery_py.lorem_ipsum.word(),
                     confirmed = True,
                     name = forgery_py.address.city(),
                     about_me = forgery_py.lorem_ipsum.sentence(),
                     member_since = forgery_py.date.date(True))
            db.session.add(u)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()

    @staticmethod
    def add_self_follows():
        for user in User.query.all():
            if not user.is_following(user):
                user.follow(user)
                db.session.add(user)
                db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class AnonymousUser(AnonymousUserMixin):
    def can(self, permissions):
        return False

    def is_administrator(self):
        return False

login_manager.anonymous_user = AnonymousUser
