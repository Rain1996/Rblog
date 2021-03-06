from datetime import datetime
from flask import render_template, url_for, request, redirect, flash, current_app, \
    abort, make_response
from flask.ext.login import login_required, current_user
from flask.ext.sqlalchemy import get_debug_queries
from . import main
from .forms import EditProfileForm, EditProfileAdminForm, PostForm, CommentForm
from .. import db
from ..models import User, Role, Permission, Post, Comment
from ..decorators import admin_required, permission_required


@main.after_app_request
def after_request(response):
    for query in get_debug_queries():
        if query.duration >= current_app.config['RBLOG_SLOW_DB_QUERY_TIME']:
            current_app.logger.warning(
                'Slow query: %s\nParamenters: %s\nDuration: %fs\nContext: %s\n'
                % (query.statement, query.paramenters, query.duration, query.context))
    return response

@main.route('/', methods = ['GET', 'POST'])
def index():
    page = request.args.get('page', 1, type = int)
    show_followed = False   # for user is not authenticated
    if current_user.is_authenticated:
        show_followed = bool(request.cookies.get('show_followed', ''))
    if show_followed:
        query = current_user.followed_posts
    else:
        query = Post.query
    pagination = query.order_by(Post.timestamp.desc()).paginate(
        page, per_page = current_app.config['RBLOG_POSTS_PER_PAGE'],
        error_out = False)
    posts = pagination.items
    return render_template('main/index.html', posts = posts,show_followed = show_followed, 
                           pagination = pagination)

@main.route('/user/<username>')
def user(username):
    user = User.query.filter_by(username = username).first()
    if user is None:
        abort(404)
    page = request.args.get('page', 1, type = int)
    pagination = user.posts.order_by(Post.timestamp.desc()).paginate(
        page, per_page = current_app.config['RBLOG_POSTS_PER_PAGE'],
        error_out = False)
    posts = pagination.items
    return render_template('main/user.html', user = user, posts = posts,
                             pagination = pagination)

@main.route('/write-blog', methods = ['GET', 'POST'])
@login_required
@permission_required(Permission.WRITE_ARTICLES)
def write_blog():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(body = form.body.data,
                    author = current_user._get_current_object())
        db.session.add(post)
        db.session.commit()
        return redirect(url_for('main.index'))
    return render_template('main/write_blog.html', form = form)

@main.route('/edit-profile', methods = ['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.location = form.location.data
        current_user.about_me = form.about_me.data
        db.session.add(current_user)
        db.session.commit()
        flash('Your profile has been updated.')
        return redirect(url_for('.user', username = current_user.username))
    form.name.data = current_user.name
    form.location.data = current_user.location
    form.about_me.data = current_user.about_me
    return render_template('main/edit_profile.html', form = form)

@main.route('/edit-profile/<int:id>', methods = ['GET', 'POST'])
@login_required
@admin_required
def edit_profile_admin(id):
    user = User.query.get_or_404(id)
    form = EditProfileAdminForm(user = user)
    if form.validate_on_submit():
        user.email = form.email.data
        user.username = form.username.data
        user.comnfirmed = form.confirmed.data
        user.role = Role.query.get(form.role.data)
        user.name = form.name.data
        user.location = form.location.data
        user.about_me = form.about_me.data
        db.session.add(user)
        db.session.commit()
        flash('The profile has been updated.')
        return redirect(url_for('.user', username = user.username))
    form.email.data = user.email
    form.username.data = user.username
    form.confirmed.data = user.confirmed
    form.role.data = user.role_id
    form.name.data = user.name
    form.location.data = user.location
    form.about_me.data = user.about_me
    return render_template('main/edit_profile_admin.html', form = form, user = user)

@main.route('/post/<int:id>', methods = ['GET', 'POST'])
def post(id):
    post = Post.query.get_or_404(id)
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(body = form.body.data, post = post,
                          author = current_user._get_current_object())
        db.session.add(comment)
        db.session.commit()
        flash("Your comment has been published.")
        return redirect(url_for('main.post', id = post.id, page = -1))
    page = request.args.get('page', 1, type = int)
    if page == -1:
        page = (post.comments.count() - 1) / \
            current_app.config['RBLOG_COMMENTS_PER_PAGE'] + 1
    pagination =  post.comments.order_by(Comment.timestamp.asc()).paginate(
        page, per_page = current_app.config['RBLOG_COMMENTS_PER_PAGE'],
        error_out = False)
    comments = pagination.items
    return render_template('main/post.html', post = post, form = form,
                            comments = comments, pagination = pagination)


@main.route('/edit/<int:id>', methods = ['GET', 'POST'])
@login_required
def edit(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and \
            not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.body = form.body.data
        post.timestamp = datetime.utcnow()   # update the time
        db.session.add(post)
        db.session.commit()
        flash('The post has been updated.')
        return redirect(url_for('main.post', id = post.id))
    form.body.data = post.body
    return render_template('main/edit_post.html', form = form)

# delete the post but it is ugly
@main.route('/confirm-delete-post/<int:id>')
@login_required
def confirm_delete_post(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and \
            not current_user.can(Permission.ADMINISTER):
        abort(403)
    return render_template('main/confirm_delete_post.html', post = post)

@main.route('/delete-post/<int:id>')
@login_required
def delete_post(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and \
            not current_user.can(Permission.ADMINISTER):
        abort(403)
    else:
        comments = post.comments.all()
        for comment in comments:
            db.session.delete(comment)
        db.session.commit()
        db.session.delete(post)
        db.session.commit()
        flash("You have deleted the post")
        return redirect(url_for('main.index'))

@main.route('/confirm-delete-comment/<int:id>')
@login_required
def confirm_delete_comment(id):
    comment = Comment.query.get_or_404(id)
    if current_user != comment.author and \
            not current_user.can(Permission.ADMINISTER):
        abort(403)
    return render_template('main/confirm_delete_comment.html', comment = comment)

@main.route('/delete-comment/<int:id>')
@login_required
def delete_comment(id):
    comment = Comment.query.get_or_404(id)
    if current_user != comment.author and \
            not current_user.can(Permission.ADMINISTER):
        abort(403)
    else:
        id = comment.post_id
        db.session.delete(comment)
        db.session.commit()
        flash("You have deleted the comment")
        return redirect(url_for('main.post', id = id))

@main.route('/follow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def follow(username):
    user = User.query.filter_by(username = username).first()
    if user is None:
        flash("Invalid user.")
        return redirect(url_for('main.index'))
    if current_user.is_following(user):
        flash('You are already following this user.')
        return redirect(url_for('main.user', username = username))
        # the one way you push the 'follow' button is on main/user/username page
    current_user.follow(user)
    db.session.commit()
    flash('You are now following %s.' % username)
    return redirect(url_for('main.user', username = username))

@main.route('/unfollow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def unfollow(username):
    user = User.query.filter_by(username = username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('main.index'))
    if not current_user.is_following(user):
        flash('You are not following this user.')
        return redirect(url_for('main.user', username = username))
    current_user.unfollow(user)
    db.session.commit()
    flash('You are not following %s anymore.' % username)
    return redirect(url_for('main.user', username = username))

@main.route('/followers/<username>')
def followers(username):
    user = User.query.filter_by(username = username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('main.index'))
    page = request.args.get('page', 1, type = int)
    pagination = user.followers.paginate(
        page, per_page = current_app.config['RBLOG_FOLLOWS_PER_PAGE'],
        error_out = False)
    follows = [{'user': item.follower, 'timestamp': item.timestamp}
                for item in pagination.items]
    return render_template('main/follows.html', user = user, title = 'Followers of',
                            endpoint = 'main.followers', pagination = pagination, follows = follows)

@main.route('/followed-by/<username>')
def followed_by(username):
    user = User.query.filter_by(username = username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('main.index'))
    page = request.args.get('page', 1, type = int)
    pagination = user.followed.paginate(
        page, per_page = current_app.config['RBLOG_FOLLOWS_PER_PAGE'],
        error_out = False)
    follows = [{'user': item.followed, 'timestamp': item.timestamp}
                for item in pagination.items]
    return render_template('main/follows.html', user = user, title = "Followed by",
                            endpoint = 'main.followed_by', pagination = pagination,
                            follows = follows)

@main.route('/all')
@login_required
def show_all():
    resp = make_response(redirect(url_for('main.index')))
    resp.set_cookie('show_followed', '', max_age = 30 * 24 * 60 * 60)
    return resp

@main.route('/followed')
@login_required
def show_followed():
    resp = make_response(redirect(url_for('main.index')))
    resp.set_cookie('show_followed', '1', max_age = 30 * 24 * 60 * 60)
    return resp

@main.route('/moderate-comments')
@login_required
@permission_required(Permission.MODERATE)
def moderate_comments():
    page = request.args.get('page', 1, type = int)
    pagination = Comment.query.order_by(Comment.timestamp.desc()).paginate(
        page, per_page = current_app.config['RBLOG_COMMENTS_PER_PAGE'],
        error_out = False)
    comments = pagination.items
    title = 'Comment'
    return render_template('main/moderate.html', comments = comments,
                           title = title, pagination = pagination, page = page)

@main.route('/moderate-comment/enable/<int:id>')
@login_required
@permission_required(Permission.MODERATE)
def moderate_comment_enable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = False
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for('main.moderate_comments',
                            page = request.args.get('page', 1, type = int)))

@main.route('/moderate-comment/disable/<int:id>')
@login_required
@permission_required(Permission.MODERATE)
def moderate_comment_disable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = True
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for('main.moderate_comments',
                            page = request.args.get('page', 1, type = int)))

@main.route('/moderate-posts')
@login_required
@permission_required(Permission.MODERATE)
def moderate_posts():
    page = request.args.get('page', 1, type = int)
    pagination = Post.query.order_by(Post.timestamp.desc()).paginate(
        page, per_page = current_app.config['RBLOG_POSTS_PER_PAGE'],
        error_out = False)
    posts = pagination.items
    title = 'Post'
    return render_template('main/moderate.html', posts = posts, title = title,
                            pagination = pagination, page = page)

@main.route('/moderate-post/enable/<int:id>')
@login_required
@permission_required(Permission.MODERATE)
def moderate_post_enable(id):
    post = Post.query.get_or_404(id)
    post.disabled = False
    db.session.add(post)
    db.session.commit()
    return redirect(url_for('main.moderate_posts',
                            page = request.args.get('page', 1, type = int)))

@main.route('/moderate-post/disable/<int:id>')
@login_required
@permission_required(Permission.MODERATE)
def moderate_post_disable(id):
    post = Post.query.get_or_404(id)
    post.disabled = True
    db.session.add(post)
    db.session.commit()
    return redirect(url_for('main.moderate_posts',
                            page = request.args.get('page', 1, type = int)))


@main.route('/shutdown')
def server_shutdown():
    if not current_app.testing:
        abort(404)
    shutdown = request.getenv('werkzeug.server.shutdown')
    if not shutdown:
        abort(500)
    shutdown()
    return 'Shutting down...'