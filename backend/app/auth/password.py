from __future__ import annotations

import hashlib
from passlib.context import CryptContext

# PBKDF2-SHA256 evita o limite de 72 bytes do bcrypt e funciona melhor no Docker/Render.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def normalize_password(password: str) -> str:
    password = (password or "").strip()
    if len(password.encode("utf-8")) > 512:
        password = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return password


def hash_password(password: str) -> str:
    return pwd_context.hash(normalize_password(password))


def verify_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(normalize_password(password), hashed_password)
