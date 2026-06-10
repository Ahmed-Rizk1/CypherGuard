#!/usr/bin/env python3
"""
Generate cryptographically secure secrets for SecureNet SOC.

Usage:
    python scripts/generate_secrets.py          # Print to stdout
    python scripts/generate_secrets.py --write  # Write to .env file (creates from .env.example)

This replaces ALL placeholder values (CHANGE-ME-*) in .env.example with
real random secrets and writes the result to .env.
"""

import os
import re
import sys
import secrets
import argparse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def generate_secret(length: int = 32) -> str:
    """Generate a cryptographically secure hex string."""
    return secrets.token_hex(length)


def generate_password(length: int = 24) -> str:
    """Generate a strong alphanumeric password."""
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main():
    parser = argparse.ArgumentParser(description="Generate SecureNet SOC secrets")
    parser.add_argument("--write", action="store_true", help="Write secrets to .env file")
    args = parser.parse_args()

    # Map of placeholder patterns to generator functions
    replacements = {
        "CHANGE-ME-use-openssl-rand-hex-32": lambda: generate_secret(32),
        "CHANGE-ME-generate-strong-password": lambda: generate_password(24),
        "CHANGE-ME-get-from-openrouter-dashboard": lambda: "YOUR_OPENROUTER_KEY_HERE",
        "CHANGE-ME-strong-grafana-password": lambda: generate_password(16),
    }

    example_path = os.path.join(PROJECT_ROOT, ".env.example")
    env_path = os.path.join(PROJECT_ROOT, ".env")

    if not os.path.exists(example_path):
        print("ERROR: .env.example not found", file=sys.stderr)
        sys.exit(1)

    with open(example_path, "r") as f:
        content = f.read()

    # Replace all placeholders
    generated = {}
    for placeholder, gen_fn in replacements.items():
        value = gen_fn()
        if placeholder in content:
            content = content.replace(placeholder, value)
            generated[placeholder] = value

    # Fix DATABASE_URL to use the actual password instead of ${POSTGRES_PASSWORD}
    # Extract POSTGRES_PASSWORD value
    pw_match = re.search(r"POSTGRES_PASSWORD=(.+)", content)
    if pw_match:
        pg_password = pw_match.group(1).strip()
        content = content.replace("${POSTGRES_PASSWORD}", pg_password)

    if args.write:
        if os.path.exists(env_path):
            # Backup existing
            backup_path = env_path + ".backup"
            os.rename(env_path, backup_path)
            print(f"Backed up existing .env to {backup_path}")

        with open(env_path, "w") as f:
            f.write(content)
        print(f"✅ Secrets written to {env_path}")
        print(f"   Generated {len(generated)} secrets:")
        for placeholder in generated:
            print(f"   - Replaced: {placeholder}")
        print("\n⚠️  Remember to set OPENROUTER_API_KEY manually if you need LLM features.")
    else:
        print("# Generated secrets (dry run — use --write to save to .env)")
        print("# " + "=" * 60)
        for placeholder, value in generated.items():
            print(f"# {placeholder} → {value[:8]}...")
        print(f"\n# Run with --write to create .env file")


if __name__ == "__main__":
    main()
