from __future__ import annotations


class HttpClient:
    """
    HTTP client injectable into Vesper services via DI.

    Declare http: HttpClient in a service __init__ to receive the
    configured client registered by HttpPlugin:

        from vesper import Injectable
        from vesper_http import HttpClient

        @Injectable()
        class WeatherService:
            def __init__(self, http: HttpClient):
                self.http = http

            def get_forecast(self, city: str) -> dict:
                resp = self.http.get(f"https://api.weather.com/v1/{city}")
                return resp["json"]

    All methods return a response dict:
        {
            "status":  200,
            "ok":      True,         # True when status < 400
            "headers": {...},
            "body":    "...",        # raw response text
            "json":    {...} | None, # parsed JSON or None
        }
    """

    def __init__(
        self,
        *,
        base_url: str = "",
        headers: dict | None = None,
        timeout: float = 30.0,
    ) -> None:
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError(
                "httpx is required by vesper-http. "
                "Install it with: pip install httpx"
            ) from exc

        self._client = httpx.Client(
            base_url=base_url,
            headers=headers or {},
            timeout=timeout,
        )

    # ── Public methods ────────────────────────────────────────────────────────

    def get(
        self,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
        timeout: float | None = None,
    ) -> dict:
        return self._request("GET", url, params=params, headers=headers, timeout=timeout)

    def post(
        self,
        url: str,
        *,
        json: dict | None = None,
        data: dict | None = None,
        headers: dict | None = None,
        timeout: float | None = None,
    ) -> dict:
        return self._request("POST", url, json=json, data=data, headers=headers, timeout=timeout)

    def put(
        self,
        url: str,
        *,
        json: dict | None = None,
        data: dict | None = None,
        headers: dict | None = None,
        timeout: float | None = None,
    ) -> dict:
        return self._request("PUT", url, json=json, data=data, headers=headers, timeout=timeout)

    def patch(
        self,
        url: str,
        *,
        json: dict | None = None,
        data: dict | None = None,
        headers: dict | None = None,
        timeout: float | None = None,
    ) -> dict:
        return self._request("PATCH", url, json=json, data=data, headers=headers, timeout=timeout)

    def delete(
        self,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
        timeout: float | None = None,
    ) -> dict:
        return self._request("DELETE", url, params=params, headers=headers, timeout=timeout)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _request(self, method: str, url: str, **kwargs) -> dict:
        # Remove None values so httpx uses its own defaults
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        resp = self._client.request(method, url, **kwargs)

        content_type = resp.headers.get("content-type", "")
        body = resp.text
        parsed_json = None
        if "json" in content_type:
            try:
                parsed_json = resp.json()
            except Exception:
                pass

        return {
            "status": resp.status_code,
            "ok": resp.status_code < 400,
            "headers": dict(resp.headers),
            "body": body,
            "json": parsed_json,
        }
