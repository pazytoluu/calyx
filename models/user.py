"""
models/user.py — Modèle SQLAlchemy représentant un utilisateur de la plateforme.

Table Oracle : USERS

Rôles possibles (contrainte CHECK en base) :
    - "admin"    : accès au panneau d'administration
    - "courtier" : accès au profil courtier
    - "client"   : accès au profil client (rôle par défaut)
"""

from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from extensions import db


class User(UserMixin, db.Model):
    """
    Représente un compte utilisateur.

    Hérite de UserMixin (Flask-Login) pour les méthodes is_authenticated,
    is_anonymous, get_id, et surcharge is_active pour refléter is_active_account.

    Relations :
        client_profile : ClientProfile (1-1, nullable)
        broker_profile : BrokerProfile (1-1, nullable)
    """

    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    email         = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name    = db.Column(db.String(100), nullable=False)
    last_name     = db.Column(db.String(100), nullable=False)
    role          = db.Column(db.String(50), nullable=False, default="client")
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    client_profile = db.relationship("ClientProfile", back_populates="user", uselist=False)
    broker_profile = db.relationship("BrokerProfile", back_populates="user", uselist=False)

    def set_password(self, raw_password):
        """
        Hache et stocke le mot de passe.

        Args:
            raw_password (str): mot de passe en clair.
        """
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        """
        Vérifie un mot de passe en clair contre le hash stocké.

        Args:
            raw_password (str): mot de passe en clair à vérifier.

        Returns:
            bool: True si le mot de passe correspond, False sinon.
        """
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_active(self):
        """
        Surcharge Flask-Login — reflète la colonne is_active_account.

        Returns:
            bool: True si le compte est actif.
        """
        return self.is_active_account

    def __repr__(self):
        return f"<User {self.email}>"
