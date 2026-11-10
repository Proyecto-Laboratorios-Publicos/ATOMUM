import asyncio
import logging
from typing import Any, Dict, Optional
import aiohttp
from aiohttp_retry import RetryClient, ExponentialRetry

log = logging.getLogger(__name__)

class AsyncHttpClient:
    """
    Cliente HTTP asíncrono reutilizable.
    - Usa un único `ClientSession` con `TCPConnector` (keep-alive + pool).
    - Soporta reintentos exponenciales y timeout configurable.
    - Opcionalmente permite limitar la concurrencia mediante un semaphore.
    """
    def __init__(
        self,
        max_connections: int = 100,
        max_keepalive: int = 30,
        timeout: float = 10.0,
        max_concurrency: Optional[int] = None,
        retry_attempts: int = 3,
        retry_factor: float = 0.5,
    ) -> None:
        connector = aiohttp.TCPConnector(
            limit=max_connections,
            ttl_dns_cache=300,
            keepalive_timeout=max_keepalive,
            ssl=False
        )
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=timeout),
        )
        # Middleware de reintentos
        self._retry_client = RetryClient(
            client=self._session,
            retry_options=ExponentialRetry(
                attempts=retry_attempts,
                start_timeout=retry_factor,
                max_timeout=timeout,
                statuses={500, 502, 503, 504},
                exceptions={aiohttp.ClientError, asyncio.TimeoutError},
            ),
        )
        # Concurrency limiter (opcional)
        self._semaphore = (
            asyncio.BoundedSemaphore(max_concurrency) if max_concurrency else None
        )

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> aiohttp.ClientResponse:
        """Ejecuta la petición dentro del semaphore (si está habilitado)."""
        async def _do():
            async with self._retry_client.request(
                method, url, json=json, params=params, headers=headers
            ) as resp:
                resp.raise_for_status()
                return resp

        if self._semaphore:
            async with self._semaphore:
                return await _do()
        return await _do()

    async def get(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        async with await self._request("GET", url, params=params, headers=headers) as resp:
            return await resp.json()

    async def post(
        self,
        url: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        async with await self._request("POST", url, json=json, headers=headers) as resp:
            return await resp.json()

    async def close(self) -> None:
        await self._retry_client.close()
        await self._session.close()
