from __future__ import annotations

from typing import Any

import requests

from .models import ApiResult
from .utils import find_published_url


class DimensurApiClient:
    def __init__(self, url: str, token: str, timeout_seconds: float = 60) -> None:
        self.url = url
        self.token = token
        self.timeout_seconds = timeout_seconds

    def publish_news(self, payload: dict[str, Any]) -> ApiResult:
        if not self.url:
            return ApiResult(False, None, "DIMENSUR_API_URL está vacío.")
        if not self.token:
            return ApiResult(False, None, "DIMENSUR_API_TOKEN está vacío.")

        try:
            response = requests.post(
                self.url,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/json",
                },
                json=payload,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            return ApiResult(False, None, f"Error de red al publicar: {exc}")

        response_json: dict[str, Any] | list[Any] | None = None
        try:
            parsed = response.json()
            if isinstance(parsed, (dict, list)):
                response_json = parsed
        except ValueError:
            pass

        success = 200 <= response.status_code < 300
        published_url = find_published_url(response_json)
        return ApiResult(
            success=success,
            status_code=response.status_code,
            response_text=response.text,
            response_json=response_json,
            published_url=published_url,
        )


def publish_news(
    payload: dict[str, Any], *, url: str, token: str, timeout_seconds: float = 60
) -> ApiResult:
    return DimensurApiClient(url, token, timeout_seconds).publish_news(payload)
