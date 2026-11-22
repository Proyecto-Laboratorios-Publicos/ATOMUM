import asyncio
import logging
from types import TracebackType
from typing import Any

import aiohttp
from aiohttp_retry import ExponentialRetry, RetryClient

log = logging.getLogger(__name__)


class AsyncHttpClient:
    """
    Cliente HTTP asíncrono reutilizable con inicialización perezosa (lazy loading)
    para evitar conflictos con el event loop de asyncio al arrancar la app.
    """

    def __init__(
        self,
        max_connections: int = 100,
        max_keepalive: int = 30,
        timeout: float = 10.0,
        max_concurrency: int | None = None,
        retry_attempts: int = 3,
        retry_factor: float = 0.5,
        verify_ssl: bool = True,
    ) -> None:
        self._max_connections = max_connections
        self._max_keepalive = max_keepalive
        self._timeout = timeout
        self._max_concurrency = max_concurrency
        self._retry_attempts = retry_attempts
        self._retry_factor = retry_factor
        self._verify_ssl = verify_ssl

        self._session: aiohttp.ClientSession | None = None
        self._retry_client: RetryClient | None = None
        self._semaphore: asyncio.BoundedSemaphore | None = None
        self._init_lock = asyncio.Lock()

    async def __aenter__(self) -> "AsyncHttpClient":
        await self._ensure_session()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def _ensure_session(self) -> None:
        """Inicializa de forma segura la sesión y el conector dentro de un event loop activo."""
        if self._session is not None and not self._session.closed and self._retry_client is not None:
            return

        async with self._init_lock:
            if self._session is None or self._session.closed:
                connector = aiohttp.TCPConnector(
                    limit=self._max_connections,
                    ttl_dns_cache=300,
                    keepalive_timeout=self._max_keepalive,
                    ssl=self._verify_ssl,
                )
                self._session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=aiohttp.ClientTimeout(total=self._timeout),
                )
                self._retry_client = RetryClient(
                    client=self._session,
                    retry_options=ExponentialRetry(
                        attempts=self._retry_attempts,
                        start_timeout=self._retry_factor,
                        max_timeout=self._timeout,
                        statuses={429, 500, 502, 503, 504},
                        exceptions={aiohttp.ClientError, asyncio.TimeoutError},
                    ),
                )
            if self._max_concurrency and self._semaphore is None:
                self._semaphore = asyncio.BoundedSemaphore(self._max_concurrency)

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        await self._ensure_session()
        assert self._retry_client is not None

        async def _do() -> dict[str, Any]:
            assert self._retry_client is not None
            async with self._retry_client.request(
                method,
                url,
                json=json,
                params=params,
                headers=headers,
            ) as resp:
                resp.raise_for_status()
                data: dict[str, Any] = await resp.json(content_type=None)
                return data

        if self._semaphore:
            async with self._semaphore:
                return await _do()
        return await _do()

    async def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return await self._request_json("GET", url, params=params, headers=headers)

    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return await self._request_json("POST", url, json=json, headers=headers)

    async def close(self) -> None:
        if self._retry_client is not None:
            await self._retry_client.close()
            self._retry_client = None
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None
