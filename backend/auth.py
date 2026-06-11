"""
JWT authentication and demo user store.
Passwords are plain-text for demo purposes — replace with hashed passwords
in any production deployment.
"""

from datetime import datetime, timedelta
from typing import Optional

from jose import jwt, JWTError

SECRET_KEY = "mediassist-dev-secret-change-in-production"
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 8

# Demo accounts matching the assignment's credential table
USERS: dict = {
    "dr.mehta":    {"password": "doctor",            "role": "doctor"},
    "nurse.priya": {"password": "nurse",             "role": "nurse"},
    "billing.ravi":{"password": "billing_executive", "role": "billing_executive"},
    "tech.anand":  {"password": "technician",        "role": "technician"},
    "admin.sys":   {"password": "admin",             "role": "admin"},
}


def authenticate_user(username: str, password: str) -> Optional[dict]:
    user = USERS.get(username)
    if user and user["password"] == password:
        return {"username": username, "role": user["role"]}
    return None


def create_access_token(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
