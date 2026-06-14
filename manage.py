#!/usr/bin/env python3
"""
SecureNet SOC — Management CLI

Provides administrative commands for the SecureNet SOC system.

Usage:
    python manage.py create-admin --email admin@securenet.local --password <strong-password>
    python manage.py create-admin --email admin@securenet.local  # prompts for password
"""

import os
import sys
import asyncio
import argparse
import getpass

import bcrypt
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uuid
from shared.database import async_session, User, DEFAULT_TENANT_ID
from sqlalchemy import select


async def create_admin(email: str, password: str, role: str = "admin") -> None:
    """Create or update an admin user with a securely hashed password."""
    if len(password) < 8:
        print("ERROR: Password must be at least 8 characters long.")
        sys.exit(1)

    # Hash the password
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    async with async_session() as session:
        # Check if user already exists
        result = await session.execute(
            select(User).where(User.email == email)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.password_hash = password_hash
            existing.role = role
            existing.is_active = True
            if not existing.tenant_id:
                existing.tenant_id = uuid.UUID(DEFAULT_TENANT_ID)
            await session.commit()
            print(f"✓ Updated existing user: {email} (role={role})")
        else:
            user = User(
                email=email,
                password_hash=password_hash,
                role=role,
                tenant_id=uuid.UUID(DEFAULT_TENANT_ID)
            )
            session.add(user)
            await session.commit()
            print(f"✓ Created new user: {email} (role={role})")


def main():
    parser = argparse.ArgumentParser(
        description="SecureNet SOC — Management CLI",
        prog="manage.py",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create-admin command
    admin_parser = subparsers.add_parser(
        "create-admin",
        help="Create or update an admin user",
    )
    admin_parser.add_argument(
        "--email",
        required=True,
        help="Admin email address",
    )
    admin_parser.add_argument(
        "--password",
        default=None,
        help="Admin password (prompted if not provided)",
    )
    admin_parser.add_argument(
        "--role",
        default="admin",
        choices=["admin", "analyst", "viewer"],
        help="User role (default: admin)",
    )

    args = parser.parse_args()

    if args.command == "create-admin":
        password = args.password
        if not password:
            password = getpass.getpass("Enter password: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("ERROR: Passwords do not match.")
                sys.exit(1)

        asyncio.run(create_admin(args.email, password, args.role))


if __name__ == "__main__":
    main()
