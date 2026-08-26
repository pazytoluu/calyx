from datetime import datetime
from extensions import db


class ClientProfile(db.Model):
    __tablename__ = "client_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    broker_id = db.Column(db.Integer, db.ForeignKey("broker_profiles.id"), nullable=True)

    phone = db.Column(db.String(30))
    address = db.Column(db.String(255))
    postal_code = db.Column(db.String(20))
    city = db.Column(db.String(100))
    insurance_type = db.Column(db.String(100))

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="client_profile")

    def __repr__(self):
        return f"<ClientProfile user_id={self.user_id}>"