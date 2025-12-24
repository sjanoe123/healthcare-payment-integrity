"""Authentication modules for API connectors.

Supports:
- OAuth2 (client credentials, authorization code)
- API Key
- Basic Auth
- Bearer Token
"""

from .oauth2 import get_oauth2_token, OAuth2Config

__all__ = [
    "get_oauth2_token",
    "OAuth2Config",
]
