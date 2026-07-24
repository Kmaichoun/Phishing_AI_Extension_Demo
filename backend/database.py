from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(BASE_DIR / ".env")


def _database_url() -> URL | str:
    explicit_url = os.getenv("DATABASE_URL", "").strip()
    if explicit_url:
        return explicit_url

    server = os.getenv("SQL_SERVER", r"localhost\SQLEXPRESS")
    database = os.getenv("SQL_DATABASE", "PhishRadarDB")
    driver = os.getenv("SQL_DRIVER", "ODBC Driver 18 for SQL Server")
    trusted = os.getenv("SQL_TRUSTED_CONNECTION", "yes")
    encrypt = os.getenv("SQL_ENCRYPT", "no")
    trust_certificate = os.getenv("SQL_TRUST_SERVER_CERTIFICATE", "yes")
    query = {
        "driver": driver,
        "Trusted_Connection": trusted,
        "Encrypt": encrypt,
        "TrustServerCertificate": trust_certificate,
    }
    return URL.create(
        "mssql+pyodbc",
        host=server,
        database=database,
        query=query,
    )


engine = create_engine(
    _database_url(),
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args={"timeout": 5},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def open_session() -> Session:
    return SessionLocal()


def database_status() -> dict[str, object]:
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT
                        CAST(1 AS bit) AS Connected,
                        DB_NAME() AS DatabaseName,
                        CAST(CASE WHEN OBJECT_ID(N'auth.Users', N'U') IS NOT NULL
                                   AND OBJECT_ID(N'auth.UserDevices', N'U') IS NOT NULL
                                   AND OBJECT_ID(N'auth.Sessions', N'U') IS NOT NULL
                                  THEN 1 ELSE 0 END AS bit) AS AuthSchemaReady,
                        CAST(CASE WHEN OBJECT_ID(N'auth.SearchHistory', N'U') IS NOT NULL
                                  THEN 1 ELSE 0 END AS bit) AS HistorySchemaReady
                    """
                )
            ).mappings().one()
        return {
            "connected": bool(row["Connected"]),
            "database": row["DatabaseName"],
            "auth_schema_ready": bool(row["AuthSchemaReady"]),
            "history_schema_ready": bool(row["HistorySchemaReady"]),
        }
    except Exception as error:
        return {
            "connected": False,
            "database": None,
            "auth_schema_ready": False,
            "history_schema_ready": False,
            "error": error.__class__.__name__,
        }
