import base64
import hashlib


def perform_hash(value, salt=""):
    return base64.b64encode(hashlib.sha256((value + salt).encode()).digest()).decode()
