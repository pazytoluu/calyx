"""
models/client_profile.py — Modèle SQLAlchemy représentant le profil d'un client.

Table Oracle : CLIENT_PROFILES

Chaque client possède exactement un profil (relation 1-1 avec users).
Un client peut être rattaché à un courtier (broker_id nullable).
"""

from datetime import datetime
from extensions import db


class ClientProfile(db.Model):
    """
    Profil étendu d'un utilisateur de rôle "client".

    Relations :
        user   : User propriétaire du profil (1-1)
        broker : BrokerProfile auquel le client est rattaché (nullable)
    """

    __tablename__ = "client_profiles"

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    broker_id    = db.Column(db.Integer, db.ForeignKey("broker_profiles.id", ondelete="SET NULL"), nullable=True)

    phone          = db.Column(db.String(30), nullable=False)
    address        = db.Column(db.String(255), nullable=False)
    postal_code    = db.Column(db.String(20), nullable=False)
    city           = db.Column(db.String(100), nullable=False)
    insurance_type = db.Column(db.String(100))   # optionnel

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user   = db.relationship("User", back_populates="client_profile")
    broker = db.relationship("BrokerProfile", back_populates="clients")

    def __repr__(self):
        return f"<ClientProfile user_id={self.user_id}>"
