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

    host = os.getenv("MYSQL_HOST", "localhost").strip()
    port = int(os.getenv("MYSQL_PORT", "3306"))
    database = os.getenv("MYSQL_DATABASE", "ip_std6730202581").strip()
    username = os.getenv("MYSQL_USER", "").strip()
    password = os.getenv("MYSQL_PASSWORD", "")
    charset = os.getenv("MYSQL_CHARSET", "utf8mb4").strip()
    return URL.create(
        "mysql+pymysql",
        username=username or None,
        password=password or None,
        host=host,
        port=port,
        database=database,
        query={"charset": charset},
    )


engine = create_engine(
    _database_url(),
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args={
        "connect_timeout": 5,
        "read_timeout": 10,
        "write_timeout": 10,
        # DATETIME values are serialized as UTC by the API, including defaults.
        "init_command": "SET time_zone = '+00:00'",
    },
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
                        1 AS Connected,
                        DATABASE() AS DatabaseName,
                        CASE WHEN (
                            SELECT COUNT(*)
                            FROM information_schema.tables
                            WHERE table_schema = DATABASE()
                              AND table_name IN ('Users', 'Sessions')
                        ) = 2 AND NOT EXISTS (
                            SELECT 1 FROM information_schema.tables
                            WHERE table_schema = DATABASE() AND table_name = 'UserDevices'
                        ) AND NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_schema = DATABASE() AND table_name = 'Sessions'
                              AND column_name = 'UserDeviceId'
                        ) THEN 1 ELSE 0 END AS AuthSchemaReady,
                        CASE WHEN EXISTS (
                            SELECT 1
                            FROM information_schema.tables
                            WHERE table_schema = DATABASE()
                              AND table_name = 'SearchHistory'
                        ) AND NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_schema = DATABASE() AND table_name = 'SearchHistory'
                              AND column_name = 'UserDeviceId'
                        ) THEN 1 ELSE 0 END AS HistorySchemaReady,
                        CASE WHEN (
                            SELECT COUNT(DISTINCT column_name)
                            FROM information_schema.columns
                            WHERE table_schema = DATABASE()
                              AND table_name = 'SearchHistory'
                              AND column_name IN ('RiskScore', 'Decision', 'ModelVersion')
                        ) = 3 THEN 1 ELSE 0 END AS RiskAuditSchemaReady,
                        CASE WHEN (
                            SELECT COUNT(*) FROM information_schema.tables
                            WHERE table_schema = DATABASE()
                              AND table_name IN ('ScanFeedback', 'AuditEvents')
                        ) = 2 THEN 1 ELSE 0 END AS WorkspaceSchemaReady
                    """
                )
            ).mappings().one()
        return {
            "connected": bool(row["Connected"]),
            "database": row["DatabaseName"],
            "auth_schema_ready": bool(row["AuthSchemaReady"]),
            "history_schema_ready": bool(row["HistorySchemaReady"]),
            "risk_audit_schema_ready": bool(row["RiskAuditSchemaReady"]),
            "workspace_schema_ready": bool(row["WorkspaceSchemaReady"]),
        }
    except Exception as error:
        return {
            "connected": False,
            "database": None,
            "auth_schema_ready": False,
            "history_schema_ready": False,
            "risk_audit_schema_ready": False,
            "workspace_schema_ready": False,
            "error": error.__class__.__name__,
        }
