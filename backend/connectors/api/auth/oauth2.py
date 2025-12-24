"""OAuth2 authentication for API connectors.

Supports:
- Client Credentials flow (machine-to-machine)
- Authorization Code flow (user authorization)
- Refresh Token flow
"""

from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None  # type: ignore


@dataclass
class OAuth2Config:
    """OAuth2 configuration."""

    token_url: str
    client_id: str
    client_secret: str
    grant_type: str = "client_credentials"
    scope: str | None = None
    audience: str | None = None

    # For authorization code flow
    authorization_url: str | None = None
    redirect_uri: str | None = None

    # For refresh token flow
    refresh_token: str | None = None

    # Additional parameters
    extra_params: dict[str, str] | None = None


class OAuth2Error(Exception):
    """Raised when OAuth2 authentication fails."""

    def __init__(self, message: str, error_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code


def get_oauth2_token(config: dict[str, Any]) -> dict[str, Any]:
    """Get an OAuth2 access token.

    Args:
        config: OAuth2 configuration dictionary with keys:
            - token_url: Token endpoint URL
            - client_id: Client ID
            - client_secret: Client secret
            - grant_type: OAuth2 grant type (default: client_credentials)
            - scope: Optional scope(s)
            - audience: Optional audience
            - refresh_token: For refresh_token grant type
            - extra_params: Additional parameters

    Returns:
        Token response with access_token, expires_in, etc.

    Raises:
        OAuth2Error: If token request fails
    """
    if not HTTPX_AVAILABLE:
        raise ImportError("httpx is required for OAuth2")

    token_url = config.get("token_url")
    client_id = config.get("client_id")
    client_secret = config.get("client_secret")
    grant_type = config.get("grant_type", "client_credentials")

    if not token_url or not client_id or not client_secret:
        raise OAuth2Error("token_url, client_id, and client_secret are required")

    # Build token request
    data: dict[str, str] = {
        "grant_type": grant_type,
    }

    # Add scope if provided
    scope = config.get("scope")
    if scope:
        data["scope"] = scope

    # Add audience if provided (common for Auth0, etc.)
    audience = config.get("audience")
    if audience:
        data["audience"] = audience

    # Handle different grant types
    if grant_type == "client_credentials":
        # Client credentials can use Basic auth or body params
        pass

    elif grant_type == "refresh_token":
        refresh_token = config.get("refresh_token")
        if not refresh_token:
            raise OAuth2Error("refresh_token is required for refresh_token grant")
        data["refresh_token"] = refresh_token

    elif grant_type == "password":
        username = config.get("username")
        password = config.get("password")
        if not username or not password:
            raise OAuth2Error("username and password are required for password grant")
        data["username"] = username
        data["password"] = password

    # Add any extra parameters
    extra_params = config.get("extra_params", {})
    if extra_params:
        data.update(extra_params)

    # Determine authentication method
    auth_method = config.get("auth_method", "basic")

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }

    if auth_method == "basic":
        # Use HTTP Basic auth
        credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        headers["Authorization"] = f"Basic {credentials}"
    else:
        # Include credentials in body
        data["client_id"] = client_id
        data["client_secret"] = client_secret

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                token_url,
                data=data,
                headers=headers,
            )

            if response.status_code == 200:
                token_data = response.json()
                logger.info(
                    f"OAuth2 token obtained, expires in {token_data.get('expires_in', 'unknown')}s"
                )
                return token_data

            # Handle error response
            try:
                error_data = response.json()
                error_code = error_data.get("error", "unknown")
                error_desc = error_data.get(
                    "error_description", f"Status {response.status_code}"
                )
                raise OAuth2Error(f"{error_code}: {error_desc}", error_code)
            except (ValueError, KeyError):
                raise OAuth2Error(
                    f"Token request failed: {response.status_code} - {response.text[:200]}"
                )

    except httpx.ConnectError as e:
        raise OAuth2Error(f"Failed to connect to token endpoint: {e}")
    except httpx.TimeoutException as e:
        raise OAuth2Error(f"Token request timed out: {e}")


class OAuth2TokenManager:
    """Manages OAuth2 token lifecycle with automatic refresh."""

    def __init__(self, config: dict[str, Any]):
        """Initialize token manager.

        Args:
            config: OAuth2 configuration
        """
        self.config = config
        self._access_token: str | None = None
        self._refresh_token: str | None = config.get("refresh_token")
        self._expires_at: float = 0

    def get_token(self) -> str:
        """Get a valid access token, refreshing if needed.

        Returns:
            Access token

        Raises:
            OAuth2Error: If unable to get valid token
        """
        # Check if current token is valid (with 60s buffer)
        if self._access_token and time.time() < self._expires_at - 60:
            return self._access_token

        # Try to refresh if we have a refresh token
        if self._refresh_token:
            try:
                return self._refresh_access_token()
            except OAuth2Error:
                logger.warning("Failed to refresh token, getting new token")

        # Get new token
        return self._get_new_token()

    def _get_new_token(self) -> str:
        """Get a new access token.

        Returns:
            Access token
        """
        token_data = get_oauth2_token(self.config)
        self._access_token = token_data["access_token"]
        self._expires_at = time.time() + token_data.get("expires_in", 3600)

        # Save refresh token if provided
        if "refresh_token" in token_data:
            self._refresh_token = token_data["refresh_token"]

        return self._access_token

    def _refresh_access_token(self) -> str:
        """Refresh the access token.

        Returns:
            New access token
        """
        refresh_config = {
            **self.config,
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
        }

        token_data = get_oauth2_token(refresh_config)
        self._access_token = token_data["access_token"]
        self._expires_at = time.time() + token_data.get("expires_in", 3600)

        # Update refresh token if new one provided
        if "refresh_token" in token_data:
            self._refresh_token = token_data["refresh_token"]

        return self._access_token

    def invalidate(self) -> None:
        """Invalidate current tokens."""
        self._access_token = None
        self._expires_at = 0


# OAuth2 provider presets for common healthcare APIs
OAUTH2_PRESETS = {
    "epic": {
        "grant_type": "client_credentials",
        "auth_method": "basic",
        "scope": "system/*.read",
    },
    "cerner": {
        "grant_type": "client_credentials",
        "auth_method": "basic",
        "scope": "system/Patient.read system/Coverage.read",
    },
    "cms_bluebutton": {
        "grant_type": "client_credentials",
        "auth_method": "body",
    },
    "smart_on_fhir": {
        "grant_type": "client_credentials",
        "auth_method": "basic",
    },
}


def get_preset_config(preset: str, **overrides: Any) -> dict[str, Any]:
    """Get OAuth2 config with provider preset.

    Args:
        preset: Provider preset name
        **overrides: Override preset values

    Returns:
        OAuth2 configuration
    """
    if preset not in OAUTH2_PRESETS:
        raise ValueError(
            f"Unknown preset: {preset}. Available: {list(OAUTH2_PRESETS.keys())}"
        )

    config = {**OAUTH2_PRESETS[preset]}
    config.update(overrides)
    return config
