"""
Firebase Auth Middleware for INTELLI-CREDIT
Verifies Firebase JWT tokens and extracts user roles.
"""

import json
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import firebase_admin
from firebase_admin import credentials, auth
from typing import Optional
import os

from config import settings


# --- Firebase Initialization ---
_firebase_app = None


def initialize_firebase():
    """Initialize Firebase Admin SDK."""
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    try:
        # Support JSON file path or inline JSON string
        service_account = settings.FIREBASE_SERVICE_ACCOUNT_JSON
        if os.path.isfile(service_account):
            cred = credentials.Certificate(service_account)
        else:
            cred = credentials.Certificate(json.loads(service_account))

        _firebase_app = firebase_admin.initialize_app(cred)
        return _firebase_app
    except Exception as e:
        print(f"[WARNING] Firebase initialization failed: {e}")
        print("[WARNING] Running without Firebase auth — development mode only")
        return None


# --- Security Scheme ---
security = HTTPBearer(auto_error=False)


# --- User Context ---
class UserContext:
    """Authenticated user context extracted from Firebase JWT."""

    def __init__(
        self,
        uid: str,
        email: str,
        role: str,
        display_name: Optional[str] = None,
        claims: Optional[dict] = None,
    ):
        self.uid = uid
        self.email = email
        self.role = role
        self.display_name = display_name
        self.claims = claims or {}

    def has_role(self, required_role: str) -> bool:
        """Check if user has the required role."""
        role_hierarchy = {
            "borrower": 0,
            "rm": 1,
            "analyst": 2,
            "credit_manager": 3,
            "sanctioning_authority": 4,
            "admin": 5,
        }
        user_level = role_hierarchy.get(self.role, -1)
        required_level = role_hierarchy.get(required_role, 999)
        return user_level >= required_level


async def verify_firebase_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> UserContext:
    """
    Verify Firebase JWT and return UserContext.
    In development mode (no Firebase), returns a mock user.
    """
    # Development mode fallback
    if _firebase_app is None:
        return UserContext(
            uid="dev-user-001",
            email="dev@intelli-credit.local",
            role="admin",
            display_name="Development User",
        )

    if credentials is None:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    token = credentials.credentials
    try:
        decoded_token = auth.verify_id_token(token)
        user_role = decoded_token.get("role", "borrower")  # Custom claim
        return UserContext(
            uid=decoded_token["uid"],
            email=decoded_token.get("email", ""),
            role=user_role,
            display_name=decoded_token.get("name"),
            claims=decoded_token,
        )
    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Authentication token has expired")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")


def require_role(required_role: str):
    """
    Dependency factory: require a specific role to access an endpoint.
    Usage: @router.get("/admin", dependencies=[Depends(require_role("admin"))])
    """
    async def role_checker(user: UserContext = Depends(verify_firebase_token)):
        if not user.has_role(required_role):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required role: {required_role}",
            )
        return user
    return role_checker


# Role-specific dependency shortcuts
get_current_user = verify_firebase_token
require_borrower = require_role("borrower")
require_rm = require_role("rm")
require_analyst = require_role("analyst")
require_credit_manager = require_role("credit_manager")
require_sanctioning = require_role("sanctioning_authority")
require_admin = require_role("admin")
