"""Integration, local-admin, and production Entra authentication."""

from __future__ import annotations

import hmac
from typing import Any, Dict, Optional

import jwt
from fastapi import Header, HTTPException
from jwt import PyJWKClient

from hc_analytics.config import Settings, get_settings

_JWK_CLIENTS: dict[str, PyJWKClient] = {}


def _bearer(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        return ""
    return authorization.split(" ", 1)[1].strip()


def require_integration(
    authorization: Optional[str] = Header(default=None),
    settings: Optional[Settings] = None,
) -> None:
    runtime = settings or get_settings()
    secret = runtime.integration_secret or ""
    provided = _bearer(authorization)
    if not secret:
        raise HTTPException(status_code=503, detail="Integration credential is not configured.")
    if not provided or not hmac.compare_digest(provided, secret):
        raise HTTPException(status_code=401, detail="Integration authentication required.")


def require_admin(
    authorization: Optional[str] = Header(default=None),
    settings: Optional[Settings] = None,
) -> None:
    runtime = settings or get_settings()
    if runtime.environment == "production":
        token = _bearer(authorization)
        if not runtime.entra_tenant_id or not runtime.entra_audience:
            raise HTTPException(
                status_code=503,
                detail="Research administration identity is not configured.",
            )
        if not token:
            raise HTTPException(
                status_code=401, detail="Research administration authentication required."
            )
        try:
            claims = _decode_entra_token(token, runtime)
        except Exception as error:
            raise HTTPException(
                status_code=401, detail="Research administration authentication required."
            ) from error
        roles = claims.get("roles")
        if not isinstance(roles, list) or runtime.entra_admin_role not in roles:
            raise HTTPException(status_code=403, detail="Research administration role required.")
        return
    secret = runtime.admin_token or ""
    provided = _bearer(authorization)
    if not secret:
        raise HTTPException(status_code=503, detail="Admin token is not configured.")
    if not provided or not hmac.compare_digest(provided, secret):
        raise HTTPException(status_code=401, detail="Admin authentication required.")


def _decode_entra_token(token: str, settings: Settings) -> Dict[str, Any]:
    """Validate a v2 Entra access token using the tenant's rotating signing keys."""
    tenant = str(settings.entra_tenant_id).strip().strip("/")
    issuer = f"https://login.microsoftonline.com/{tenant}/v2.0"
    jwks_url = f"https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys"
    client = _JWK_CLIENTS.setdefault(
        jwks_url,
        PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=3600),
    )
    signing_key = client.get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=settings.entra_audience,
        issuer=issuer,
        options={"require": ["exp", "iat", "nbf", "iss", "aud", "sub"]},
        leeway=30,
    )
    if claims.get("tid") != tenant:
        raise jwt.InvalidTokenError("Token tenant does not match.")
    return claims


def assert_same_origin_mutation(headers, *, required: bool) -> None:
    if not required:
        return
    if headers.get("x-medastrax-request") != "1":
        raise HTTPException(status_code=403, detail="Request was not accepted.")
