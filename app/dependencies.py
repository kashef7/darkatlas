from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from app.config import settings

# Absolute path ensures Swagger UI's "Authorize" lock points to the correct endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user_role(token: str = Depends(oauth2_scheme)) -> str:
    """Statelessly decodes and validates incoming JWT. Returns the user's role claim."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        role: str | None = payload.get("role")
        username: str | None = payload.get("sub")
        if role is None or username is None:
            raise credentials_exception
        return role
    except JWTError:
        raise credentials_exception


class RoleChecker:
    """Parametric RBAC checker — enforces stateless role-based access before touching service layers."""

    def __init__(self, allowed_roles: list[str]) -> None:
        self.allowed_roles = allowed_roles

    def __call__(self, role: str = Depends(get_current_user_role)) -> str:
        if role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted. Insufficient permissions.",
            )
        return role


# Pre-configured RBAC dependency shortcuts
require_admin = RoleChecker(["admin"])
require_editor_or_admin = RoleChecker(["admin", "editor"])
