"""Home page and account-related routes."""
from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from database import db
from models import User


def register_auth_routes(app):
    @app.get("/")
    def index():
        return render_template("index.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            gender = request.form.get("gender", "")
            if not all((name, email, password, gender)):
                flash("All fields are required.", "danger")
            elif len(password) < 8:
                flash("Password must be at least 8 characters.", "danger")
            elif User.query.filter_by(email=email).first():
                flash("Email already registered.", "danger")
            else:
                user = User(name=name, email=email, password_hash=generate_password_hash(password), gender=gender)
                db.session.add(user)
                db.session.commit()
                session.clear()
                session["user_id"] = user.user_id
                flash("Account created.", "success")
                return redirect(url_for("dashboard"))
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            user = User.query.filter_by(email=email).first()
            if user and check_password_hash(user.password_hash, request.form.get("password", "")):
                session.clear()
                session["user_id"] = user.user_id
                return redirect(request.args.get("next") or url_for("dashboard"))
            flash("Invalid email or password.", "danger")
        return render_template("login.html")

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("index"))
