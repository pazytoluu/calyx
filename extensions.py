"""
extensions.py — Instanciation des extensions Flask partagées.

Les extensions sont créées ici sans être liées à une app Flask spécifique
(pattern Application Factory). L'initialisation effective se fait dans app.py
via les appels init_app(app).

Extensions :
    db           : SQLAlchemy — ORM et gestion de la base de données Oracle
    migrate      : Flask-Migrate — migrations de schéma via Alembic
    login_manager: Flask-Login — gestion des sessions utilisateur

Configuration Flask-Login :
    login_view             : nom de la route de connexion ("login")
    login_message          : message affiché si accès non autorisé
    login_message_category : catégorie du message flash ("info")
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

db            = SQLAlchemy()
migrate       = Migrate()
login_manager = LoginManager()

login_manager.login_view             = "login"
login_manager.login_message          = "Veuillez vous connecter pour accéder à cette page."
login_manager.login_message_category = "info"
