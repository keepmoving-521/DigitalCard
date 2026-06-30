import argparse
from getpass import getpass

from sqlalchemy import select

from digitalcard.core.errors import AppError
from digitalcard.db.session import SessionLocal
from digitalcard.models.account import User, UserRole
from digitalcard.schemas.account import normalize_email
from digitalcard.services.passwords import hash_password, validate_password


def create_admin(email: str, display_name: str) -> None:
    normalized_email = normalize_email(email)
    password = getpass("Administrator password: ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    try:
        validate_password(password, normalized_email)
    except AppError as exc:
        requirements = ", ".join(exc.details.get("requirements", [])) if exc.details else ""
        raise SystemExit(f"{exc.message}: {requirements}") from exc
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email == normalized_email)):
            raise SystemExit("An account with this email already exists")
        user = User(
            email=normalized_email,
            display_name=display_name.strip(),
            password_hash=hash_password(password),
            role=UserRole.ADMIN.value,
            must_change_password=False,
        )
        db.add(user)
        db.commit()
    print(f"Administrator created: {normalized_email}")


def main() -> None:
    parser = argparse.ArgumentParser(description="DigitalCard administration commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create-admin", help="Create the first administrator")
    create_parser.add_argument("--email", required=True)
    create_parser.add_argument("--name", required=True)
    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin(args.email, args.name)


if __name__ == "__main__":
    main()
