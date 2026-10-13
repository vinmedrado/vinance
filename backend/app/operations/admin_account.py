from __future__ import annotations

import argparse
import asyncio
from getpass import getpass

from backend.app.auth.normalization import normalize_email
from backend.app.auth.security import get_password_hash
from backend.app.auth.service import get_user_by_email
from backend.app.auth.sessions import revoke_all_user_sessions
from backend.app.core.database import AsyncSessionLocal


async def reset_password(email: str) -> int:
    first = getpass("New password: ")
    second = getpass("Confirm new password: ")
    if first != second or len(first) < 8 or len(first) > 128:
        print("Password confirmation failed or length is outside 8..128 characters.")
        return 2
    async with AsyncSessionLocal() as session:
        user = await get_user_by_email(session, normalize_email(email))
        if user is None:
            print("Account not found.")
            return 1
        user.hashed_password = get_password_hash(first)
        await revoke_all_user_sessions(session, user.id)
        await session.commit()
    print("Password updated and all sessions revoked.")
    return 0


async def revoke_sessions(email: str) -> int:
    async with AsyncSessionLocal() as session:
        user = await get_user_by_email(session, normalize_email(email))
        if user is None:
            print("Account not found.")
            return 1
        await revoke_all_user_sessions(session, user.id)
        await session.commit()
    print("All sessions revoked.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="VinanceOS trusted account recovery")
    parser.add_argument("action", choices=("reset-password", "revoke-sessions"))
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    if args.action == "reset-password":
        return asyncio.run(reset_password(args.email))
    return asyncio.run(revoke_sessions(args.email))


if __name__ == "__main__":
    raise SystemExit(main())
