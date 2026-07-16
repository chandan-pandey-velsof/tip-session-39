import requests
from django.conf import settings


class TipApiError(Exception):
    """Raised when the TIP API returns a non-2xx response."""
    pass


class TipClient:
    """Thin HTTP client for calling the TIP API from a generated preview app."""

    def __init__(self, base_url: str = None, token: str = None):
        self.base_url = (base_url or settings.TIP_API_URL).rstrip('/')
        self.token = token or settings.TIP_API_TOKEN
        self._session = requests.Session()
        self._session.headers.update({
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
        })

    def get(self, endpoint: str, params: dict = None) -> dict:
        """GET {base_url}/{endpoint} and return parsed JSON."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        resp = self._session.get(url, params=params or {})
        if not resp.ok:
            raise TipApiError(f"GET {endpoint} failed: {resp.status_code} {resp.text[:200]}")
        return resp.json()

    def post(self, endpoint: str, data: dict = None) -> dict:
        """POST {base_url}/{endpoint} with JSON body and return parsed JSON."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        resp = self._session.post(url, json=data or {})
        if not resp.ok:
            raise TipApiError(f"POST {endpoint} failed: {resp.status_code} {resp.text[:200]}")
        return resp.json()


def get_tip_client() -> TipClient:
    """Factory — returns a TipClient using settings from Django settings."""
    return TipClient()
