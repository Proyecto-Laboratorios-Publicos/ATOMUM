import asyncio
import logging
from typing import Any, Dict, Optional
import aiohttp
from aiohttp_retry import RetryClient, ExponentialRetry

log = logging.getLogger(__name__)

class AsyncHttpClient:
    """
    Cliente HTTP asíncrono reutilizable con inicialización perezosa (lazy loading)
    para evitar conflictos con el event loop de asyncio al arrancar la app.
    """
    def __init__(self, max_connections: int = 100, max_keepalive: int = 30, timeout: float = 10.0, max_concurrency: Optional[int] = None, retry_attempts: int = 3, retry_factor: float = 0.5) -> None:
        self._max_connections = max_connections
        self._max_keepalive = max_keepalive
        self._timeout = timeout
        self._max_concurrency = max_concurrency
        self._retry_attempts = retry_attempts
        self._retry_factor = retry_factor
        
        self._session: Optional[aiohttp.ClientSession] = None
        self._retry_client: Optional[RetryClient] = None
        self._semaphore: Optional[asyncio.BoundedSemaphore] = None

    async def _ensure_session(self) -> None:
        """Inicializa la sesión y el conector dentro de un bucle de eventos activo."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=self._max_connections,
                ttl_dns_cache=300,
                keepalive_timeout=self._max_keepalive,
                ssl=False
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
                    statuses={500, 502, 503, 504},
                    exceptions={aiohttp.ClientError, asyncio.TimeoutError},
                ),
            )
            if self._max_concurrency and self._semaphore is None:
                self._semaphore = asyncio.BoundedSemaphore(self._max_concurrency)

    async def _request(self, method: str, url: str, *, json: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> aiohttp.ClientResponse:
        await self._ensure_session()
        async def _do():
            async with self._retry_client.request(method, url, json=json, params=params, headers=headers) as resp:
                resp.raise_for_status()
                return resp
        if self._semaphore:
            async with self._semaphore:
                return await _do()
        return await _do()

    async def get(self, url: str, *, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        async with await self._request("GET", url, params=params, headers=headers) as resp:
            return await resp.json()

    async def post(self, url: str, *, json: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        async with await self._request("POST", url, json=json, headers=headers) as resp:
            return await resp.json()

    async def close(self) -> None:
        if self._retry_client:
            await self._retry_client.close()
        if self._session and not self._session.closed:
            await self._session.close()
