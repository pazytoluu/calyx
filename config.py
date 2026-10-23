"""
config.py — Configuration de l'application Calyx.

Les valeurs sensibles (credentials, clé secrète) sont chargées depuis
un fichier .env via python-dotenv. Ne jamais committer le fichier .env.

Variables d'environnement attendues (.env) :
    SECRET_KEY     : clé secrète Flask pour les sessions et CSRF
    superuser      : nom d'utilisateur Oracle
    superpwd       : mot de passe Oracle
    ORACLE_HOST    : hôte Oracle (défaut: localhost)
    ORACLE_PORT    : port Oracle (défaut: 1521)
    ORACLE_SERVICE : nom du service Oracle (défaut: FREEPDB1)
"""

import os
from dotenv import load_dotenv

load_dotenv()

ORACLE_USER    = os.environ.get("superuser")
ORACLE_PASSWORD = os.environ.get("superpwd")
ORACLE_HOST    = os.environ.get("ORACLE_HOST", "localhost")
ORACLE_PORT    = os.environ.get("ORACLE_PORT", "1521")
ORACLE_SERVICE = os.environ.get("ORACLE_SERVICE", "FREEPDB1")


class Config:
    """
    Configuration Flask chargée via app.config.from_object('config.Config').

    Attributs :
        SECRET_KEY                  : clé secrète pour les sessions Flask.
        SQLALCHEMY_DATABASE_URI     : DSN Oracle en mode thin (python-oracledb),
                                      ne nécessite pas d'Oracle Client installé.
        SQLALCHEMY_TRACK_MODIFICATIONS : désactivé pour éviter l'overhead SQLAlchemy.
    """

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev")

    SQLALCHEMY_DATABASE_URI = (
        f"oracle+oracledb://{ORACLE_USER}:{ORACLE_PASSWORD}"
        f"@{ORACLE_HOST}:{ORACLE_PORT}/?service_name={ORACLE_SERVICE}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    STRIPE_PUBLIC_KEY      = os.environ.get("STRIPE_PUBLIC_KEY")
    STRIPE_SECRET_KEY      = os.environ.get("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET  = os.environ.get("STRIPE_WEBHOOK_SECRET")

    UPLOAD_FOLDER          = os.path.join(os.path.dirname(__file__), "static", "uploads")
    MAX_CONTENT_LENGTH     = 10 * 1024 * 1024  # 10 MB max par requête
