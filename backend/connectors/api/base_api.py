"""Base API connector with retry and rate limiting.

Provides common functionality for REST and FHIR API connectors including:
- HTTP client with connection pooling
- Exponential backoff retry logic
- Rate limiting
- Authentication handling
"""

from __future__ import annotations

import logging
import time
from abc import abstractmethod
from typing import Any, Iterator

from ..base import BaseConnector, SyncMode
from ..models import ConnectionTestResult, ConnectorType

logger = logging.getLogger(__name__)

# Try to import httpx for async HTTP
try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None  # type: ignore
    logger.warning("httpx not installed - API connectors disabled")


class APIConnectionError(Exception):
    """Raised when API connection fails."""

    def __init__(self, message: str, connector_id: str, status_code: int | None = None):
        super().__init__(message)
        self.connector_id = connector_id
        self.status_code = status_code


class RateLimitError(APIConnectionError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        connector_id: str,
        retry_after: int | None = None,
    ):
        super().__init__(message, connector_id, status_code=429)
        self.retry_after = retry_after


class BaseAPIConnector(BaseConnector):
    """Base class for API-based connectors.

    Provides:
    - HTTP client with configurable timeout and pooling
    - Exponential backoff retry logic
    - Rate limiting with configurable requests per second
    - Authentication header injection
    """

    connector_type = ConnectorType.API

    def __init__(
        self,
        connector_id: str,
        name: str,
        config: dict[str, Any],
        batch_size: int = 100,
    ) -> None:
        """Initialize API connector.

        Args:
            connector_id: Unique identifier
            name: Human-readable name
            config: API configuration with keys:
                - base_url: API base URL
                - auth_type: none, api_key, basic, bearer, oauth2
                - api_key: API key (for api_key auth)
                - api_key_header: Header name for API key (default: X-API-Key)
                - username: Username (for basic auth)
                - password: Password (for basic auth)
                - bearer_token: Bearer token (for bearer auth)
                - oauth2_config: OAuth2 settings (for oauth2 auth)
                - timeout: Request timeout in seconds (default: 30)
                - max_retries: Maximum retry attempts (default: 3)
                - retry_delay: Initial retry delay in seconds (default: 1)
                - rate_limit: Max requests per second (default: 10)
                - verify_ssl: Verify SSL certificates (default: True)
            batch_size: Records per batch
        """
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx is required. Install with: pip install httpx")

        super().__init__(connector_id, name, config, batch_size)
        self._client: httpx.Client | None = None
        self._last_request_time: float = 0
        self._request_interval: float = 1.0 / config.get("rate_limit", 10)

        # Retry settings
        self._max_retries = config.get("max_retries", 3)
        self._retry_delay = config.get("retry_delay", 1)

        # Token cache for OAuth2
        self._access_token: str | None = None
        self._token_expires_at: float = 0

    def connect(self) -> None:
        """Establish API connection."""
        if self._connected:
            return

        try:
            base_url = self.config.get("base_url")
            if not base_url:
                raise ValueError("base_url is required")

            timeout = httpx.Timeout(
                self.config.get("timeout", 30),
                connect=10.0,
            )

            self._client = httpx.Client(
                base_url=base_url,
                timeout=timeout,
                verify=self.config.get("verify_ssl", True),
                follow_redirects=True,
            )

            self._connected = True
            self._log("info", f"Connected to API: {base_url}")

        except Exception as e:
            raise APIConnectionError(
                f"Failed to connect to API: {e}",
                self.connector_id,
            ) from e

    def disconnect(self) -> None:
        """Disconnect from API."""
        if self._client:
            self._client.close()
            self._client = None
        super().disconnect()

    def test_connection(self) -> ConnectionTestResult:
        """Test API connection."""
        start_time = time.time()

        try:
            base_url = self.config.get("base_url")
            if not base_url:
                return ConnectionTestResult(
                    success=False,
                    message="base_url is required",
                    latency_ms=None,
                    details={},
                )

            # Create temporary client for testing
            timeout = httpx.Timeout(10.0, connect=5.0)
            with httpx.Client(
                base_url=base_url,
                timeout=timeout,
                verify=self.config.get("verify_ssl", True),
            ) as client:
                # Get auth headers
                headers = self._get_auth_headers()

                # Try health endpoint or base URL
                health_endpoint = self.config.get("health_endpoint", "/")
                response = client.get(health_endpoint, headers=headers)

                latency_ms = (time.time() - start_time) * 1000

                if response.status_code < 400:
                    return ConnectionTestResult(
                        success=True,
                        message=f"Successfully connected to API: {base_url}",
                        latency_ms=round(latency_ms, 2),
                        details={
                            "base_url": base_url,
                            "status_code": response.status_code,
                            "auth_type": self.config.get("auth_type", "none"),
                        },
                    )
                else:
                    return ConnectionTestResult(
                        success=False,
                        message=f"API returned status {response.status_code}",
                        latency_ms=round(latency_ms, 2),
                        details={
                            "status_code": response.status_code,
                            "response": response.text[:500],
                        },
                    )

        except httpx.ConnectError as e:
            return ConnectionTestResult(
                success=False,
                message=f"Connection error: {str(e)[:200]}",
                latency_ms=None,
                details={"error_type": "ConnectError"},
            )
        except httpx.TimeoutException as e:
            latency_ms = (time.time() - start_time) * 1000
            return ConnectionTestResult(
                success=False,
                message=f"Connection timeout: {str(e)[:200]}",
                latency_ms=round(latency_ms, 2),
                details={"error_type": "TimeoutException"},
            )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"Connection failed: {str(e)[:200]}",
                latency_ms=None,
                details={"error_type": type(e).__name__},
            )

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers based on auth_type.

        Returns:
            Dictionary of headers to add to requests
        """
        auth_type = self.config.get("auth_type", "none")
        headers: dict[str, str] = {}

        if auth_type == "api_key":
            api_key = self.config.get("api_key")
            header_name = self.config.get("api_key_header", "X-API-Key")
            if api_key:
                headers[header_name] = api_key

        elif auth_type == "basic":
            import base64

            username = self.config.get("username", "")
            password = self.config.get("password", "")
            credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {credentials}"

        elif auth_type == "bearer":
            token = self.config.get("bearer_token")
            if token:
                headers["Authorization"] = f"Bearer {token}"

        elif auth_type == "oauth2":
            token = self._get_oauth2_token()
            if token:
                headers["Authorization"] = f"Bearer {token}"

        return headers

    def _get_oauth2_token(self) -> str | None:
        """Get OAuth2 access token, refreshing if needed.

        Returns:
            Access token or None
        """
        # Check if we have a valid cached token
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        oauth2_config = self.config.get("oauth2_config", {})
        token_url = oauth2_config.get("token_url")

        if not token_url:
            logger.warning("OAuth2 token_url not configured")
            return None

        try:
            from .auth.oauth2 import get_oauth2_token

            token_data = get_oauth2_token(oauth2_config)
            self._access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)
            self._token_expires_at = time.time() + expires_in

            return self._access_token

        except Exception as e:
            logger.error(f"Failed to get OAuth2 token: {e}")
            return None

    def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_interval:
            time.sleep(self._request_interval - elapsed)
        self._last_request_time = time.time()

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make an HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            json_data: JSON request body
            headers: Additional headers

        Returns:
            HTTP response

        Raises:
            APIConnectionError: If request fails after retries
            RateLimitError: If rate limit exceeded
        """
        if not self._client:
            self.connect()

        # Merge auth headers
        request_headers = self._get_auth_headers()
        if headers:
            request_headers.update(headers)

        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                # Apply rate limiting
                self._rate_limit()

                response = self._client.request(
                    method=method,
                    url=endpoint,
                    params=params,
                    json=json_data,
                    headers=request_headers,
                )

                # Check for rate limit
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    retry_seconds = int(retry_after) if retry_after else 60
                    raise RateLimitError(
                        f"Rate limit exceeded, retry after {retry_seconds}s",
                        self.connector_id,
                        retry_after=retry_seconds,
                    )

                # Check for server errors (retry)
                if response.status_code >= 500:
                    raise APIConnectionError(
                        f"Server error: {response.status_code}",
                        self.connector_id,
                        status_code=response.status_code,
                    )

                # Check for client errors (don't retry)
                if response.status_code >= 400:
                    raise APIConnectionError(
                        f"Client error: {response.status_code} - {response.text[:200]}",
                        self.connector_id,
                        status_code=response.status_code,
                    )

                return response

            except RateLimitError:
                raise
            except APIConnectionError as e:
                last_error = e
                if e.status_code and e.status_code < 500:
                    raise  # Don't retry client errors

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e

            # Exponential backoff
            if attempt < self._max_retries:
                delay = self._retry_delay * (2**attempt)
                self._log(
                    "warning", f"Request failed, retrying in {delay}s: {last_error}"
                )
                time.sleep(delay)

        raise APIConnectionError(
            f"Request failed after {self._max_retries + 1} attempts: {last_error}",
            self.connector_id,
        )

    def _get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make a GET request.

        Args:
            endpoint: API endpoint
            params: Query parameters
            headers: Additional headers

        Returns:
            HTTP response
        """
        return self._request("GET", endpoint, params=params, headers=headers)

    def _post(
        self,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make a POST request.

        Args:
            endpoint: API endpoint
            json_data: JSON request body
            params: Query parameters
            headers: Additional headers

        Returns:
            HTTP response
        """
        return self._request(
            "POST", endpoint, params=params, json_data=json_data, headers=headers
        )

    @abstractmethod
    def extract(
        self,
        sync_mode: SyncMode,
        watermark_value: str | None = None,
    ) -> Iterator[list[dict[str, Any]]]:
        """Extract data from API.

        Args:
            sync_mode: Full or incremental sync
            watermark_value: Last sync watermark for incremental

        Yields:
            Batches of records
        """
        pass

    @abstractmethod
    def discover_schema(self) -> dict[str, Any]:
        """Discover API schema/resources.

        Returns:
            Schema information
        """
        pass
