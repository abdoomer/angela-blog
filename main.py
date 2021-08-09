from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)

# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")  # 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# CONFIGURE TABLES

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)

    # Create Foreign Key, "users.id" the users refers to the table name of User.
    author_id = db.Column(db.Integer, db.ForeignKey("Users.id"))
    # Create reference to the User object, the "posts" refers to the posts property in the User class.
    author = relationship("User", back_populates="posts")

    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comment", back_populates="parent_post")


class User(UserMixin, db.Model):
    __tablename__ = "Users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)

    # This will act like a List of BlogPost objects attached to each User.
    # The "author" refers to the author property in the BlogPost class.
    comments = relationship("Comment", back_populates="comment_author")
    posts = relationship("BlogPost", back_populates="author")


# One To Many Creating relationship between User table and BlogPost table
class Comment(UserMixin, db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("Users.id"))
    comment_author = relationship("User", back_populates="comments")
    text = db.Column(db.Text, nullable=False)
    parent_post = relationship("BlogPost", back_populates="comments")
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))


db.create_all()

# Login Manger
login_manager = LoginManager()
login_manager.init_app(app)

# Initialize with flask to auto generate users photos
# Angela original photo url = "https://pbs.twimg.com/profile_images/744849215675838464/IH0FNIXk.jpg"
gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False, force_lower=False, use_ssl=False,
                    base_url=None)


# Checking if the logged in user has the id = 1, which means he is the admin and will be granted access to
# edit post, create new post or delete a certain post
def admin_only(function):
    @wraps(function)
    def wrapper():
        if current_user.id == 1:
            return function()
        else:
            return abort(403)
            # return "<h1>Forbidden</h1>" \
            #        "<p>You don't have the permission to access the requested resources. It's either read protected" \
            #        " or not readable by the server</p>"
    return wrapper


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    users = User.query.all()
    return render_template("index.html", all_posts=posts, logged_in=current_user.is_active, all_users=users)


@app.route('/register', methods=["POST", "GET"])
def register():
    error = None
    login_form = LoginForm()
    register_form = RegisterForm()
    if request.method == "POST":
        name = request.form["name"]
        password = request.form["password"]
        email = request.form["email"]
        user = User.query.filter_by(email=email).first()
        if user is None:
            encrypt_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)
            new_user = User(name=name, password=encrypt_password, email=email)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for("get_all_posts", logged_in=current_user.is_active))
        else:
            error = "You have already signed up with that email, log in instead!"
            return render_template("login.html", error=error, form=login_form, logged_in=current_user.is_active)
    elif request.method == "GET":
        return render_template("register.html", form=register_form, logged_in=current_user.is_active)


@app.route('/login', methods=["POST", "GET"])
def login():
    login_form = LoginForm()
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()
        if user is None:
            error = "the Email you entered doesn't exist, please try again!"
            return render_template("login.html", error=error, form=login_form, logged_in=current_user.is_active)
        else:
            if check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for("get_all_posts"))
            else:
                error = "Password Incorrect, Please try again!"
                return render_template("login.html", error=error, form=login_form, logged_in=current_user.is_active)
    elif request.method == "GET":
        error = request.args["error"]
        return render_template("login.html", form=login_form, error=error, logged_in=current_user.is_active)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts', logged_in=current_user.is_active))


@app.route("/post/<int:post_id>", methods=["POST", "GET"])
def show_post(post_id):
    comment_form = CommentForm()
    if request.method == "GET":
        all_comments = Comment.query.all()
        requested_post = BlogPost.query.get(post_id)
        author_name = User.query.filter_by(id=requested_post.author_id).first().name
        return render_template("post.html", post=requested_post, logged_in=current_user.is_active,
                               author_name=author_name, form=comment_form, comments=all_comments)
    elif request.method == "POST":
        if current_user.is_active:
            if comment_form.validate_on_submit():
                new_comment = Comment(author_id=current_user.id, text=comment_form.comment.data, post_id=post_id)
                db.session.add(new_comment)
                db.session.commit()
                return redirect(url_for("get_all_posts"))
        else:
            error = "You need to logged first in in order to be able to add comments!"
            return redirect(url_for("login", error=error))


@app.route("/about")
def about():
    return render_template("about.html", logged_in=current_user.is_active)


@app.route("/contact")
def contact():
    return render_template("contact.html", logged_in=current_user.is_active)


@app.route("/new-post", methods=["POST", "GET"])
@login_required
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, logged_in=current_user.is_active)


@app.route("/edit-post/<int:post_id>")
@login_required
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id, logged_in=current_user.is_active))

    return render_template("make-post.html", form=edit_form, logged_in=current_user.is_active)


@app.route("/delete/<int:post_id>")
@login_required
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts', logged_in=current_user.is_active))


if __name__ == "__main__":
    app.run(debug=True)   # host='0.0.0.0', port=5000
