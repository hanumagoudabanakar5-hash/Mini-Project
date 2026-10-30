from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, Admin

auth = Blueprint("auth", __name__)


@auth.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("auth.register"))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "danger")
            return redirect(url_for("auth.register"))

        existing_admin = Admin.query.filter(
            (Admin.username == username) |
            (Admin.email == email)
        ).first()

        if existing_admin:
            flash("Username or email already exists.", "danger")
            return redirect(url_for("auth.register"))

        hashed_password = generate_password_hash(password)

        new_admin = Admin(
            username=username,
            email=email,
            password=hashed_password
        )

        db.session.add(new_admin)
        db.session.commit()

        flash("Registration successful! Please login.", "success")

        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("auth.dashboard"))

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        admin = Admin.query.filter_by(email=email).first()

        if admin and check_password_hash(admin.password, password):

            login_user(admin)

            return redirect(url_for("auth.dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@auth.route("/dashboard")
@login_required
def dashboard():

    return render_template("dashboard.html")


@auth.route("/logout", methods=["POST"])
@login_required
def logout():

    logout_user()

    flash("Logged out successfully.", "success")

    return redirect(url_for("auth.login"))
