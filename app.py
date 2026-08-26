import re
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import login_user
from models.client_profile import ClientProfile
from extensions import db, migrate, login_manager
from models.user import User

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-moi-en-prod'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --- Routes ---
EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PASSWORD_REGEX = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\w\s]).{8,}$")


@app.route('/')
def index():
    return render_template('index.html')


@app.route("/connexion", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # --- Validation serveur ---
        if not EMAIL_REGEX.match(email):
            flash("Merci de saisir une adresse email valide.", "error")
            return render_template("login.html"), 400

        if not PASSWORD_REGEX.match(password):
            flash(
                "Le mot de passe doit contenir au moins 8 caractères, "
                "une majuscule, une minuscule, un chiffre et un caractère spécial.",
                "error",
            )
            return render_template("login.html"), 400

        # --- Authentification ---
        user = User.query.filter_by(email=email).first()

        if user is None or not user.check_password(password):
            flash("Email ou mot de passe incorrect.", "error")
            return render_template("login.html"), 401

        if not user.is_active_account:
            flash("Ce compte a été désactivé.", "error")
            return render_template("login.html"), 403

        login_user(user)
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/inscription", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # --- Validation des champs texte ---
        if not first_name or not last_name:
            flash("Merci de renseigner votre prénom et votre nom.", "error")
            return render_template("register.html"), 400

        # --- Validation email ---
        if not EMAIL_REGEX.match(email):
            flash("Merci de saisir une adresse email valide.", "error")
            return render_template("register.html"), 400

        # --- Email déjà utilisé ? ---
        if User.query.filter_by(email=email).first() is not None:
            flash("Un compte existe déjà avec cette adresse email.", "error")
            return render_template("register.html"), 409

        # --- Validation mot de passe ---
        if not PASSWORD_REGEX.match(password):
            flash(
                "Le mot de passe doit contenir au moins 8 caractères, "
                "une majuscule, une minuscule, un chiffre et un caractère spécial.",
                "error",
            )
            return render_template("register.html"), 400

        if password != confirm_password:
            flash("Les mots de passe ne correspondent pas.", "error")
            return render_template("register.html"), 400

        # --- Création du compte (role client fixé en dur, jamais depuis le formulaire) ---
        new_user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            role="client",
        )
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.flush()  # pour récupérer new_user.id avant le commit

        new_client_profile = ClientProfile(user_id=new_user.id)
        db.session.add(new_client_profile)

        db.session.commit()

        flash("Compte créé avec succès. Vous pouvez vous connecter.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


if __name__ == '__main__':
    app.run(debug=True)
