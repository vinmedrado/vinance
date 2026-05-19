from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def ensure_auth_schema(db: Session) -> None:
    """Garante a base mínima de autenticação SaaS.

    Este patch é intencionalmente incremental: ele não remove tabelas antigas,
    não recria schema existente e só cria o que falta para cadastro/login real.
    Em produção, Alembic continua sendo o caminho ideal; esta função protege o
    ambiente local/Render inicial quando as migrations ainda não foram aplicadas.
    """
    statements = [
        """
        CREATE TABLE IF NOT EXISTS organizations (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(255) UNIQUE,
            plan VARCHAR(40) DEFAULT 'free',
            subscription_status VARCHAR(40) DEFAULT 'trialing',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS users (
            id VARCHAR(36) PRIMARY KEY,
            email VARCHAR(255) NOT NULL UNIQUE,
            hashed_password VARCHAR(255) NOT NULL,
            full_name VARCHAR(255),
            is_active BOOLEAN DEFAULT TRUE,
            email_verified_at TIMESTAMPTZ,
            last_login_at TIMESTAMPTZ,
            tenant_id VARCHAR(36),
            role VARCHAR(80),
            plan VARCHAR(40),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS organization_members (
            id SERIAL PRIMARY KEY,
            organization_id VARCHAR(36) NOT NULL,
            user_id VARCHAR(36) NOT NULL,
            role VARCHAR(80) NOT NULL DEFAULT 'member',
            is_active BOOLEAN DEFAULT TRUE,
            invited_by VARCHAR(36),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_org_member_user UNIQUE (organization_id, user_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS subscriptions (
            id SERIAL PRIMARY KEY,
            organization_id VARCHAR(36) NOT NULL,
            plan VARCHAR(40) DEFAULT 'free',
            status VARCHAR(40) DEFAULT 'trialing',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS user_sessions (
            id VARCHAR(36) PRIMARY KEY,
            organization_id VARCHAR(36),
            user_id VARCHAR(36) NOT NULL,
            refresh_token_hash VARCHAR(128) NOT NULL UNIQUE,
            ip_address VARCHAR(80),
            user_agent VARCHAR(500),
            revoked_at TIMESTAMPTZ,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id VARCHAR(36) PRIMARY KEY,
            organization_id VARCHAR(36),
            user_id VARCHAR(36) NOT NULL,
            session_id VARCHAR(36),
            token_hash VARCHAR(128) NOT NULL UNIQUE,
            replaced_by_hash VARCHAR(128),
            revoked_at TIMESTAMPTZ,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS roles (
            name VARCHAR(80) PRIMARY KEY,
            description TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS permissions (
            name VARCHAR(160) PRIMARY KEY,
            description TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS role_permissions (
            role_name VARCHAR(80) NOT NULL,
            permission_name VARCHAR(160) NOT NULL,
            PRIMARY KEY (role_name, permission_name)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            organization_id VARCHAR(36),
            user_id VARCHAR(36),
            action VARCHAR(160) NOT NULL,
            entity_type VARCHAR(120),
            entity_id VARCHAR(120),
            before_json TEXT,
            after_json TEXT,
            ip_address VARCHAR(80),
            user_agent VARCHAR(500),
            request_id VARCHAR(80),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)",
        "CREATE INDEX IF NOT EXISTS ix_users_tenant_id ON users (tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_org_members_user ON organization_members (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_org_members_org ON organization_members (organization_id)",
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_org ON audit_logs (organization_id)",
    ]
    for stmt in statements:
        db.execute(text(stmt))
    db.commit()
