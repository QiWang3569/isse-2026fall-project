"""Versioned, salted password hashes using the standard library's scrypt KDF."""
import base64
import hashlib
import hmac
import re
import secrets


N = 2 ** 15
R = 8
P = 3
MAXMEM = 64 * 1024 * 1024
VERSION = 'scrypt_v1'


def new_password_error(password: str) -> str | None:
    if not 9 <= len(password) <= 128 or not re.search(r'[A-Za-z]', password) or not re.search(r'[0-9]', password):
        return '密码需为 9–128 位，且同时包含英文字母和数字'
    return None


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=N, r=R, p=P,
                            maxmem=MAXMEM, dklen=32)
    return f'{VERSION}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}'


def verify_password(password: str, encoded: str) -> bool:
    try:
        version, raw_salt, raw_digest = encoded.split('$')
        if version != VERSION:
            return False
        salt = base64.b64decode(raw_salt, altchars=b'-_', validate=True)
        expected = base64.b64decode(raw_digest, altchars=b'-_', validate=True)
        if len(salt) != 16 or len(expected) != 32:
            return False
    except (ValueError, UnicodeError):
        return False
    actual = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=N, r=R, p=P,
                            maxmem=MAXMEM, dklen=32)
    return hmac.compare_digest(actual, expected)


DUMMY_HASH = hash_password('dummy password that is never accepted')
