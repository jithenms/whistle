import base64
import hashlib
import secrets


def perform_hash(value, salt=""):
    return base64.b64encode(hashlib.sha256((value + salt).encode()).digest()).decode()


def generate_api_credentials():
    api_key = secrets.token_urlsafe(32)
    api_secret = secrets.token_urlsafe(64)
    api_secret_salt = secrets.token_urlsafe(8)

    return (
        api_key,
        api_secret,
        api_secret_salt,
    )
