from __future__ import annotations

from pathlib import Path

from vesper.core.plugin import VesperPlugin
from vesper_http.client import HttpClient


class HttpPlugin(VesperPlugin):
    """
    HTTP client plugin for Vesper.

    Solves CORS by proxying external HTTP requests through Python instead of
    making them directly from the WebView.

    Provides two integration points:
      1. DI injection — services declare http: HttpClient to receive the client.
      2. IPC commands — http:get/post/put/patch/delete callable directly from JS.

    Usage:
        from vesper import App
        from vesper_http import HttpPlugin

        app = App(
            root_module=AppModule,
            plugins=[HttpPlugin(base_url="https://api.example.com")],
        )

    Services use the injected client for business logic:
        from vesper import Injectable
        from vesper_http import HttpClient

        @Injectable()
        class ProductsService:
            def __init__(self, http: HttpClient):
                self.http = http

            def fetch_products(self) -> list:
                resp = self.http.get("/products")
                return resp["json"]

    JS can also call the commands directly for simple proxy use cases:
        const data = await vesper.http.get("https://api.example.com/products")
    """

    def __init__(
        self,
        *,
        base_url: str = "",
        headers: dict | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url
        self._headers = headers or {}
        self._timeout = timeout

    def register(self, app) -> None:
        client = HttpClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=self._timeout,
        )

        # Register in per-App DI — services that declare http: HttpClient get this instance
        app.register_global_provider(HttpClient, client)

        # Also expose as IPC commands for direct use from JS
        @app.command("http:get")
        def http_get(
            url: str,
            params: dict = None,
            headers: dict = None,
            timeout: float = None,
        ) -> dict:
            return client.get(url, params=params, headers=headers, timeout=timeout)

        @app.command("http:post")
        def http_post(
            url: str,
            json: dict = None,
            data: dict = None,
            headers: dict = None,
            timeout: float = None,
        ) -> dict:
            return client.post(url, json=json, data=data, headers=headers, timeout=timeout)

        @app.command("http:put")
        def http_put(
            url: str,
            json: dict = None,
            data: dict = None,
            headers: dict = None,
            timeout: float = None,
        ) -> dict:
            return client.put(url, json=json, data=data, headers=headers, timeout=timeout)

        @app.command("http:patch")
        def http_patch(
            url: str,
            json: dict = None,
            data: dict = None,
            headers: dict = None,
            timeout: float = None,
        ) -> dict:
            return client.patch(url, json=json, data=data, headers=headers, timeout=timeout)

        @app.command("http:delete")
        def http_delete(
            url: str,
            params: dict = None,
            headers: dict = None,
            timeout: float = None,
        ) -> dict:
            return client.delete(url, params=params, headers=headers, timeout=timeout)

    @classmethod
    def sdk_path(cls) -> Path | None:
        from importlib.resources import files
        return Path(str(files("vesper_http").joinpath("sdk/vesper-http.js")))
