"""Authentication helpers and dependencies."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from itsdangerous import URLSafeSerializer


SESSION_USER_KEY = "tcm_user"
SESSION_CSRF_KEY = "tcm_csrf"


@dataclass
class UserSession:
    username: str
    role: str


class AuthManager:
    def __init__(self, secret_key: str) -> None:
        self.serializer = URLSafeSerializer(secret_key, salt="csrf")

    def issue_csrf(self, session: Dict[str, str]) -> str:
        token = self.serializer.dumps({"nonce": secrets.token_hex(16)})
        session[SESSION_CSRF_KEY] = token
        return token

    def verify_csrf(self, session: Dict[str, str], token: str) -> bool:
        stored = session.get(SESSION_CSRF_KEY)
        if not stored or stored != token:
            return False
        try:
            self.serializer.loads(token)
            return True
        except Exception:
            return False


def get_current_user(request: Request) -> Optional[UserSession]:
    data = request.session.get(SESSION_USER_KEY)
    if not data:
        return None
    return UserSession(username=data["username"], role=data["role"])


def require_role(role: str) -> Callable[[UserSession], UserSession]:
    def dependency(user: UserSession = Depends(get_authenticated_user)) -> UserSession:
        if user.role not in {role, "serwis"} and role != "operator":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges")
        return user

    return dependency


def get_authenticated_user(user: Optional[UserSession] = Depends(get_current_user)) -> UserSession:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user

