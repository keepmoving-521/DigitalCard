import re
from functools import lru_cache

from pwdlib import PasswordHash

from digitalcard.core.errors import AppError


@lru_cache
def password_hasher() -> PasswordHash:
    return PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher().hash(password)


def verify_password(password: str, password_hash: str) -> tuple[bool, str | None]:
    return password_hasher().verify_and_update(password, password_hash)


@lru_cache
def dummy_password_hash() -> str:
    return hash_password("DigitalCard-Dummy-Password-Only-For-Timing-2026!")


def validate_password(password: str, email: str | None = None) -> None:
    violations: list[str] = []
    if len(password) < 12:
        violations.append("at_least_12_characters")
    if not re.search(r"[a-z]", password):
        violations.append("lowercase_letter")
    if not re.search(r"[A-Z]", password):
        violations.append("uppercase_letter")
    if not re.search(r"\d", password):
        violations.append("number")
    if not re.search(r"[^\w\s]", password):
        violations.append("special_character")
    if email:
        local_part = email.split("@", maxsplit=1)[0].lower()
        if len(local_part) >= 3 and local_part in password.lower():
            violations.append("must_not_contain_email")
    if violations:
        raise AppError(
            "weak_password",
            "Password does not meet the security requirements",
            422,
            {"requirements": violations},
        )
