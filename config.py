import os
from dotenv import load_dotenv

load_dotenv()

ORACLE_USER = os.environ.get("superuser")
ORACLE_PASSWORD = os.environ.get("superpwd")
ORACLE_HOST = os.environ.get("ORACLE_HOST", "localhost")
ORACLE_PORT = os.environ.get("ORACLE_PORT", "1521")
ORACLE_SERVICE = os.environ.get("FREEPDB1")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev")

    # DSN Oracle au format python-oracledb (mode "thin", pas besoin d'Oracle Client)
    SQLALCHEMY_DATABASE_URI = (
        f"oracle+oracledb://{ORACLE_USER}:{ORACLE_PASSWORD}"
        f"@{ORACLE_HOST}:{ORACLE_PORT}/?service_name={ORACLE_SERVICE}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False