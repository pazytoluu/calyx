"""
app.py — Point d'entrée principal de l'application Calyx.

Initialise l'application Flask, configure les extensions (SQLAlchemy, Flask-Migrate,
Flask-Login), enregistre les routes et les gestionnaires d'erreurs.

Rôles utilisateurs :
    - admin    : accès au panneau d'administration (/admin)
    - courtier : profil courtier (à venir)
    - client   : profil client (/profil)
"""

import logging
import os
import re
import uuid
import stripe
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from models.client_profile import ClientProfile
from models.broker_profile import BrokerProfile
from models.order import Order
from models.audit import Audit, AuditFile, allowed_file
from extensions import db, migrate, login_manager
from models.user import User
from logger import init_logging

app = Flask(__name__)
app.config.from_object('config.Config')

db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)
init_logging(app)
stripe.api_key = app.config["STRIPE_SECRET_KEY"]

auth_log  = logging.getLogger("calyx.auth")
error_log = logging.getLogger("calyx.error")


@login_manager.user_loader
def load_user(user_id):
    """
    Callback Flask-Login — recharge l'utilisateur depuis la session.

    Args:
        user_id (str): identifiant stocké dans le cookie de session.

    Returns:
        User | None: instance User correspondante, ou None si introuvable.
    """
    return User.query.get(int(user_id))


# Expressions régulières de validation partagées entre les routes
EMAIL_REGEX    = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PASSWORD_REGEX = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\w\s]).{8,}$")


# ---------------------------------------------------------------------------
# Routes publiques
# ---------------------------------------------------------------------------

@app.route("/playbook")
def book():
    """
    Affiche la page produit du Playbook Relation Client.

    Returns:
        Response: rendu de Book.html avec le dict `product` contenant
                  title, price, image (nom de fichier static) et description.
    """
    product = {
        "title": "Playbook Relation Client",
        "price": "300,00 €",
        "image": "livre.avif",
        "description": (
            "Une solution pour les courtiers d'assurance. Le but ? Mieux "
            "gérer les insatisfactions, éviter les erreurs qui coûtent du "
            "temps et des clients, et adopter une méthode claire face aux "
            "situations sensibles."
        ),
    }
    return render_template("Book.html", product=product)


@app.route("/playbook/commander")
def book_checkout():
    """
    Affiche la page de commande / paiement du Playbook.

    Returns:
        Response: rendu de bookcheckout.html.
    """
    return render_template("bookcheckout.html")


@app.route('/')
def index():
    """
    Page d'accueil publique.

    Returns:
        Response: rendu de index.html.
    """
    return render_template('index.html')


@app.route("/connexion", methods=["GET", "POST"])
def login():
    """
    Gère l'authentification des utilisateurs.

    GET  : affiche le formulaire de connexion.
    POST : valide les champs, vérifie les credentials, connecte l'utilisateur
           et redirige selon son rôle :
               - admin    → /admin
               - autres   → /profil

    Validations :
        - Format email (EMAIL_REGEX)
        - Format mot de passe (PASSWORD_REGEX)
        - Existence du compte et correspondance du mot de passe
        - Compte actif (is_active_account)

    Codes HTTP retournés :
        400 : champ invalide
        401 : credentials incorrects
        403 : compte désactivé

    Returns:
        Response: redirection ou rendu de login.html.
    """
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

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

        user = User.query.filter_by(email=email).first()

        if user is None or not user.check_password(password):
            auth_log.warning("Tentative de connexion échouée pour : %s [IP: %s]", email, request.remote_addr)
            flash("Email ou mot de passe incorrect.", "error")
            return render_template("login.html"), 401

        if not user.is_active_account:
            auth_log.warning("Connexion refusée — compte désactivé : %s", email)
            flash("Ce compte a été désactivé.", "error")
            return render_template("login.html"), 403

        login_user(user)
        auth_log.info("Connexion réussie : %s (rôle=%s) [IP: %s]", email, user.role, request.remote_addr)

        if user.role == "admin":
            return redirect(url_for("superuser_view"))
        return redirect(url_for("client_profile"))

    return render_template("login.html")


@app.route("/inscription", methods=["GET", "POST"])
def register():
    """
    Gère la création d'un compte client.

    GET  : affiche le formulaire d'inscription.
    POST : valide les champs, crée un User (rôle=client par défaut) et
           un ClientProfile associé dans une transaction atomique.

    Validations :
        - Prénom et nom non vides
        - Téléphone, adresse, code postal, ville non vides
        - Format email (EMAIL_REGEX)
        - Email non déjà utilisé
        - Format mot de passe (PASSWORD_REGEX)
        - Confirmation du mot de passe

    Codes HTTP retournés :
        400 : champ invalide
        409 : email déjà utilisé
        500 : erreur base de données (avec rollback)

    Returns:
        Response: redirection vers /connexion ou rendu de register.html.
    """
    if request.method == "POST":
        first_name       = request.form.get("first_name", "").strip()
        last_name        = request.form.get("last_name", "").strip()
        email            = request.form.get("email", "").strip().lower()
        password         = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        phone            = request.form.get("phone", "").strip()
        address          = request.form.get("address", "").strip()
        postal_code      = request.form.get("postal_code", "").strip()
        city             = request.form.get("city", "").strip()

        if not first_name or not last_name:
            flash("Merci de renseigner votre prénom et votre nom.", "error")
            return render_template("register.html"), 400

        if not phone or not address or not postal_code or not city:
            flash("Merci de renseigner votre téléphone, adresse, code postal et ville.", "error")
            return render_template("register.html"), 400

        if not EMAIL_REGEX.match(email):
            flash("Merci de saisir une adresse email valide.", "error")
            return render_template("register.html"), 400

        if User.query.filter_by(email=email).first() is not None:
            auth_log.warning("Inscription refusée — email déjà utilisé : %s", email)
            flash("Un compte existe déjà avec cette adresse email.", "error")
            return render_template("register.html"), 409

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

        try:
            new_user = User(first_name=first_name, last_name=last_name, email=email)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.flush()  # récupère new_user.id avant le commit

            new_client_profile = ClientProfile(
                user_id=new_user.id,
                phone=phone,
                address=address,
                postal_code=postal_code,
                city=city,
            )
            db.session.add(new_client_profile)
            db.session.commit()

            auth_log.info("Nouveau compte créé : %s [IP: %s]", email, request.remote_addr)
            flash("Compte créé avec succès. Vous pouvez vous connecter.", "success")
            return redirect(url_for("login"))

        except Exception as e:
            db.session.rollback()
            error_log.exception("Erreur lors de la création du compte %s : %s", email, e)
            flash("Une erreur est survenue. Veuillez réessayer.", "error")
            return render_template("register.html"), 500

    return render_template("register.html")


# ---------------------------------------------------------------------------
# Routes audit
# ---------------------------------------------------------------------------

@app.route("/audit")
def audit_offer():
    """
    Page de présentation de l'offre audit (3 audits pour 1500€).
    Accessible à tous, mais le bouton souscrire redirige vers connexion si non connecté.
    """
    return render_template("audit_offer.html")


@app.route("/audit/paiement")
@login_required
def audit_checkout():
    """
    Crée une session Stripe Checkout pour le pack 3 audits (1500€).
    Redirige vers Stripe, puis retour sur /audit/succes ou /audit/annule.
    """
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {"name": "Pack Audit — 3 dossiers"},
                "unit_amount": 150000,  # 1500.00 € en centimes
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=url_for("audit_success", _external=True) + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=url_for("audit_cancel", _external=True),
        metadata={"user_id": current_user.id},
    )
    return redirect(session.url, code=303)


@app.route("/audit/succes")
@login_required
def audit_success():
    """
    Page de confirmation après paiement Stripe réussi.
    Crée la commande en base avec status='paid' et 3 slots d'audit.
    """
    session_id = request.args.get("session_id")
    if not session_id:
        return redirect(url_for("audit_offer"))

    # Vérifie que la session n'a pas déjà été traitée
    existing = Order.query.filter_by(stripe_session_id=session_id).first()
    if not existing:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == "paid":
                order = Order(
                    user_id=current_user.id,
                    stripe_session_id=session_id,
                    status="paid",
                    amount_paid=1500.00,
                    audit_slots_total=3,
                    audit_slots_used=0,
                )
                db.session.add(order)
                db.session.commit()
                app.logger.info("Commande audit créée pour %s (session=%s)", current_user.email, session_id)
        except Exception as e:
            error_log.exception("Erreur création commande après paiement : %s", e)

    order = Order.query.filter_by(stripe_session_id=session_id).first()
    return render_template("audit_success.html", order=order)


@app.route("/audit/annule")
@login_required
def audit_cancel():
    """Page affichée si le client annule le paiement Stripe."""
    flash("Paiement annulé.", "error")
    return redirect(url_for("audit_offer"))


@app.route("/audit/soumettre", methods=["GET", "POST"])
@login_required
def audit_submit():
    """
    Formulaire de soumission d'un dossier d'audit.
    Accessible uniquement aux clients ayant une commande payée avec des slots restants.
    """
    profile = current_user.client_profile
    if not profile:
        flash("Profil client introuvable.", "error")
        return redirect(url_for("client_profile"))

    # Cherche une commande payée avec des slots disponibles
    order = Order.query.filter(
        Order.user_id == current_user.id,
        Order.status == "paid",
        Order.audit_slots_used < Order.audit_slots_total,
    ).first()

    if not order:
        flash("Vous n'avez pas de pack audit actif ou tous vos slots sont utilisés.", "error")
        return redirect(url_for("audit_offer"))

    if request.method == "POST":
        title       = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        priority    = request.form.get("priority", "medium")
        files       = request.files.getlist("files")

        if not title:
            flash("Le titre est obligatoire.", "error")
            return render_template("audit_submit.html", order=order), 400

        if priority not in ("low", "medium", "high"):
            priority = "medium"

        try:
            audit = Audit(
                client_id=profile.id,
                order_id=order.id,
                title=title,
                description=description,
                priority=priority,
            )
            db.session.add(audit)
            db.session.flush()

            upload_folder = app.config["UPLOAD_FOLDER"]
            os.makedirs(upload_folder, exist_ok=True)

            for f in files:
                if f and f.filename and allowed_file(f.filename):
                    ext         = f.filename.rsplit(".", 1)[1].lower()
                    stored_name = f"{uuid.uuid4().hex}.{ext}"
                    f.save(os.path.join(upload_folder, stored_name))
                    db.session.add(AuditFile(
                        audit_id=audit.id,
                        filename=secure_filename(f.filename),
                        stored_name=stored_name,
                        mime_type=f.mimetype,
                        file_size=f.seek(0, 2) or 0,
                    ))

            order.audit_slots_used += 1
            db.session.commit()

            app.logger.info("Audit soumis par %s (id=%s)", current_user.email, audit.id)
            flash("Votre dossier a été soumis avec succès.", "success")
            return redirect(url_for("client_profile"))

        except Exception as e:
            db.session.rollback()
            error_log.exception("Erreur soumission audit : %s", e)
            flash("Une erreur est survenue. Veuillez réessayer.", "error")

    return render_template("audit_submit.html", order=order)


@app.route("/admin/audits/assigner", methods=["POST"])
@login_required
def assign_audit():
    """
    Assigne un audit à un courtier (admin uniquement).
    Champs POST : audit_id, broker_id
    """
    if current_user.role != "admin":
        return redirect(url_for("client_profile"))

    audit_id  = request.form.get("audit_id", type=int)
    broker_id = request.form.get("broker_id", type=int)

    audit  = Audit.query.get(audit_id)
    broker = BrokerProfile.query.get(broker_id)

    if not audit or not broker:
        flash("Audit ou courtier introuvable.", "error")
        return redirect(url_for("superuser_view"))

    try:
        from datetime import datetime
        audit.broker_id   = broker.id
        audit.status      = "assigned"
        audit.assigned_at = datetime.utcnow()
        db.session.commit()
        app.logger.info("Audit %s assigné au courtier %s par %s", audit_id, broker.company_name, current_user.email)
        flash(f"Audit assigné à {broker.company_name}.", "success")
    except Exception as e:
        db.session.rollback()
        error_log.exception("Erreur assignation audit %s : %s", audit_id, e)
        flash("Une erreur est survenue.", "error")

    return redirect(url_for("superuser_view"))


# ---------------------------------------------------------------------------
# Routes admin (rôle = "admin" requis)
# ---------------------------------------------------------------------------

@app.route("/admin/creer-courtier", methods=["POST"])
@login_required
def create_broker():
    """
    Crée un compte courtier (User + BrokerProfile).

    Accessible uniquement aux utilisateurs avec rôle admin.
    Crée atomiquement un User (rôle=courtier) et son BrokerProfile associé.

    Champs requis (POST) :
        first_name, last_name, email, password, company_name,
        orias_number, phone, address, postal_code, city

    Champs optionnels :
        siret

    Validations :
        - Tous les champs requis non vides
        - Format email (EMAIL_REGEX)
        - Format mot de passe (PASSWORD_REGEX)
        - Email non déjà utilisé

    Returns:
        Response: redirection vers /admin avec message flash.
    """
    if current_user.role != "admin":
        return redirect(url_for("client_profile"))

    first_name   = request.form.get("first_name", "").strip()
    last_name    = request.form.get("last_name", "").strip()
    email        = request.form.get("email", "").strip().lower()
    password     = request.form.get("password", "")
    company_name = request.form.get("company_name", "").strip()
    orias_number = request.form.get("orias_number", "").strip()
    siret        = request.form.get("siret", "").strip()
    phone        = request.form.get("phone", "").strip()
    address      = request.form.get("address", "").strip()
    postal_code  = request.form.get("postal_code", "").strip()
    city         = request.form.get("city", "").strip()

    if not all([first_name, last_name, email, password, company_name, orias_number, phone, address, postal_code, city]):
        flash("Tous les champs obligatoires doivent être remplis.", "error")
        return redirect(url_for("superuser_view"))

    if not EMAIL_REGEX.match(email):
        flash("Adresse email invalide.", "error")
        return redirect(url_for("superuser_view"))

    if not PASSWORD_REGEX.match(password):
        flash("Mot de passe invalide (8 car. min, maj, min, chiffre, spécial).", "error")
        return redirect(url_for("superuser_view"))

    if User.query.filter_by(email=email).first():
        flash("Un compte existe déjà avec cet email.", "error")
        return redirect(url_for("superuser_view"))

    try:
        new_user = User(first_name=first_name, last_name=last_name, email=email, role="courtier")
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.flush()

        new_broker = BrokerProfile(
            user_id=new_user.id,
            company_name=company_name,
            orias_number=orias_number,
            siret=siret or None,
            phone=phone,
            address=address,
            postal_code=postal_code,
            city=city,
        )
        db.session.add(new_broker)
        db.session.commit()

        auth_log.info("Courtier créé par admin %s : %s", current_user.email, email)
        flash(f"Courtier {first_name} {last_name} créé avec succès.", "success")

    except Exception as e:
        db.session.rollback()
        error_log.exception("Erreur création courtier %s : %s", email, e)
        flash("Une erreur est survenue.", "error")

    return redirect(url_for("superuser_view"))


@app.route("/admin")
@login_required
def superuser_view():
    """
    Panneau d'administration.

    Accessible uniquement aux utilisateurs avec rôle admin.
    Redirige vers /profil si l'utilisateur n'est pas admin.

    Returns:
        Response: rendu de Superuserpov.html avec l'utilisateur courant.
    """
    if current_user.role != "admin":
        app.logger.warning("Accès /admin refusé pour %s (rôle=%s)", current_user.email, current_user.role)
        return redirect(url_for("client_profile"))
    app.logger.info("Accès admin par %s", current_user.email)
    audits  = Audit.query.order_by(Audit.created_at.desc()).all()
    brokers = BrokerProfile.query.all()
    return render_template("Superuserpov.html", user=current_user, audits=audits, brokers=brokers)


# ---------------------------------------------------------------------------
# Routes authentifiées
# ---------------------------------------------------------------------------

@app.route("/profil")
@login_required
def client_profile():
    """
    Affiche le profil du client connecté.

    Passe à la template :
        user    : instance User (current_user)
        profile : instance ClientProfile liée, ou None si absente

    Returns:
        Response: rendu de ClientProfile.html.
    """
    return render_template("ClientProfile.html", user=current_user, profile=current_user.client_profile)


@app.route("/deconnexion")
@login_required
def logout():
    """
    Déconnecte l'utilisateur courant et redirige vers la page d'accueil.

    Returns:
        Response: redirection vers /.
    """
    auth_log.info("Déconnexion : %s", current_user.email)
    logout_user()
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Gestionnaires d'erreurs
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    """Retourne la page 404 personnalisée."""
    error_log.warning("404 — %s %s", request.method, request.path)
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    """Retourne la page 500 personnalisée et logue l'exception complète."""
    error_log.exception("500 — %s %s : %s", request.method, request.path, e)
    return render_template("500.html"), 500


if __name__ == '__main__':
    app.run(debug=True)
