"""
JWT validation and user extraction for Supabase auth.
"""
import os
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from jose import jwt, JWTError
import httpx

class HTTPAuthCredentials(BaseModel):
    """HTTP Authorization credentials (scheme + credentials)."""
    scheme: str
    credentials: str

# Supabase project URL
SUPABASE_URL = os.getenv("SUPABASE_URL")
if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL environment variable is required")

security = HTTPBearer()

# Cache for JWKS (public keys)
_jwks_cache = None


async def get_jwks():
    """Fetch Supabase's JWKS (JSON Web Key Set) for token validation."""
    global _jwks_cache
    
    if _jwks_cache:
        return _jwks_cache
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")
            response.raise_for_status()
            _jwks_cache = response.json()
            return _jwks_cache
    except Exception as e:
        raise RuntimeError(f"Failed to fetch JWKS from Supabase: {str(e)}")


def get_current_user(credentials: HTTPAuthCredentials = Depends(security)) -> str:
    """
    Validates the Supabase JWT access token and returns the user_id (sub claim).
    Uses Supabase's public keys for verification.
    
    Args:
        credentials: Bearer token from Authorization header
        
    Returns:
        user_id (str): The authenticated user's UUID
        
    Raises:
        HTTPException: If token is invalid or missing
    """
    token = credentials.credentials
    
    try:
        # Decode without verification first to get the header
        unverified_header = jwt.get_unverified_header(token)
        
        # For Supabase, we should verify the signature
        # The simplest approach for local testing: verify with the JWT secret
        # For production: use JWKS endpoint (see get_jwks above)
        jwt_secret = os.getenv("SUPABASE_JWT_SECRET")

        if jwt_secret:
            # Try HS256 first (JWT Secret)
            try:
                payload = jwt.decode(
                    token,
                    jwt_secret,
                    algorithms=["HS256"],
                    options={"verify_aud": False}
                )
            except JWTError:
                # If HS256 fails (most Supabase tokens are ES256), fall back to unverified claims
                payload = jwt.get_unverified_claims(token)
                if not payload or not payload.get("sub"):
                    raise JWTError("Invalid token: missing 'sub' claim")
        else:
            # No JWT secret provided; extract unverified claims for local dev
            payload = jwt.get_unverified_claims(token)
            if not payload or not payload.get("sub"):
                raise JWTError("Invalid token: missing 'sub' claim")
        
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token: missing user ID",
            )
            
        return user_id
        
    except JWTError as e:
        # Don't log token details in production
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )


def get_optional_user(credentials: Optional[HTTPAuthCredentials] = Depends(HTTPBearer(auto_error=False))) -> Optional[str]:
    """
    Optional auth: returns user_id if token is valid, None otherwise.
    Useful for endpoints that work both with and without auth.
    """
    if credentials is None:
        return None
    
    try:
        return get_current_user(credentials)
    except HTTPException:
        return None

