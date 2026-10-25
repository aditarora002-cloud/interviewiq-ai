"""Email/password accounts with PBKDF2 password hashes and revocable bearer sessions."""
import hashlib
import hmac
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from . import db

PBKDF2_ROUNDS = 390_000
SESSION_DAYS = 30
bearer = HTTPBearer(auto_error=False)


class RegisterBody(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class LoginBody(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str


def email_normalized(email):
    email = email.strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise HTTPException(status_code=422, detail='Enter a valid email address.')
    return email


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf8'), salt, PBKDF2_ROUNDS)
    return f'pbkdf2_sha256${PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}'


def verify_password(password, stored):
    try:
        alg, rounds, salt, check = stored.split('$')
        if alg != 'pbkdf2_sha256': return False
        result = hashlib.pbkdf2_hmac('sha256', password.encode('utf8'), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(result, bytes.fromhex(check))
    except (ValueError, TypeError):
        return False


def issue_token(user):
    token = secrets.token_urlsafe(36)
    db.save_token(hashlib.sha256(token.encode()).hexdigest(), user['id'],
                  (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat())
    return {'token': token, 'token_type': 'bearer', 'user': {'id': user['id'], 'name': user['name'], 'email': user['email']}}


def register(payload):
    email = email_normalized(payload.email)
    if db.user_by_email(email):
        raise HTTPException(409, 'An account with this email already exists.')
    user = {'id': str(uuid.uuid4()), 'email': email, 'name': payload.name.strip()}
    try:
        db.create_user(user['id'], email, user['name'], hash_password(payload.password))
    except Exception as exc:
        if db.user_by_email(email):
            raise HTTPException(409, 'An account with this email already exists.') from exc
        raise
    return issue_token(user)


def login(payload):
    user = db.user_by_email(email_normalized(payload.email))
    if not user or not verify_password(payload.password, user['password_hash']):
        raise HTTPException(401, 'Invalid email or password.')
    return issue_token(user)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials or credentials.scheme.lower() != 'bearer':
        raise HTTPException(401, 'Please sign in to continue.', headers={'WWW-Authenticate': 'Bearer'})
    token_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    user = db.user_by_token(token_hash)
    if not user:
        raise HTTPException(401, 'Your session has expired. Please sign in again.', headers={'WWW-Authenticate': 'Bearer'})
    return user


def logout(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), user=Depends(current_user)):
    db.revoke_token(hashlib.sha256(credentials.credentials.encode()).hexdigest())
    return {'success': True}
