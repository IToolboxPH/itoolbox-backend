"""Set a new password on a BantAI account, for an admin when someone has forgotten
theirs. The web app has no reset of its own. Run it inside the API container,
which has the database settings:

    docker exec -it itoolbox-api python reset_password.py

It asks for the email and the new password, which is never echoed or passed on
the command line.
"""
from __future__ import annotations

import asyncio
import getpass
import sys

from sqlalchemy import text

from database import AsyncSessionLocal, engine
from modules.auth.local_auth import hash_password

MIN_PASSWORD = 10  # CreateUserRequest's minimum


async def reset(email: str, password: str) -> bool:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text("UPDATE user_credentials SET hashed_password = :pw, updated_at = now() WHERE email = :email"),
                {"pw": hash_password(password), "email": email},
            )
            await db.commit()
            return result.rowcount == 1
    finally:
        await engine.dispose()


def ask_password(prompt: str) -> str:
    # Input piped from Windows ends each line with \r\n, and getpass keeps the \r.
    return getpass.getpass(prompt).rstrip("\r")


def main() -> int:
    email = input("Email: ").strip().lower()
    password = ask_password("New password: ")
    if len(password) < MIN_PASSWORD:
        print(f"The password needs at least {MIN_PASSWORD} characters.")
        return 1
    if ask_password("New password again: ") != password:
        print("The two passwords differ.")
        return 1
    if not asyncio.run(reset(email, password)):
        print(f"No account has the email {email}.")
        return 1
    print(f"New password set for {email}. They can change it under Account after signing in.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
