# core.py
"""
Motor asíncrono de escaneo de puertos TCP.
- Utiliza asyncio + semaphore para limitar la concurrencia.
- Emite callbacks (on_open, on_close, on_error) para que la UI o cualquier otro consumidor pueda reaccionar a cada evento.
- Soporta timeout configurable y reintentos opcionales.
"""
import asyncio
import socket
from typing import Callable, Iterable, List, Tuple, Optional, Dict

# ----------------------------------------------------------------------
# Tipos de callback
# ----------------------------------------------------------------------
PortResult = Tuple[str, int, bool]  # (host, port, is_open)
OnOpenCallback = Callable[[PortResult], None]
OnCloseCallback = Callable[[PortResult], None]
OnErrorCallback = Callable[[str, Exception], None]

# ----------------------------------------------------------------------
# Helper interno: intento de conexión TCP
# ----------------------------------------------------------------------
async def _probe(
    host: str,
    port: int,
    timeout: float,
    *,
    on_open: Optional[OnOpenCallback] = None,
    on_close: Optional[OnCloseCallback] = None,
    on_error: Optional[OnErrorCallback] = None
) -> None:
    """
    Intenta abrir una conexión TCP al (host, port).
    Llama al callback correspondiente según el resultado.
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        # Si llega aquí, el puerto está abierto
        if on_open:
            on_open((host, port, True))
        
        # Cerramos la conexión de forma limpia
        writer.close()
        await writer.wait_closed()
        
        if on_close:
            on_close((host, port, True))
            
    except asyncio.TimeoutError as exc:
        if on_close:
            on_close((host, port, False))
        if on_error:
            on_error(f"Timeout {host}:{port}", exc)
    except (ConnectionRefusedError, OSError) as exc:
        if on_close:
            on_close((host, port, False))
        if on_error:
            on_error(f"Connection error {host}:{port}", exc)
    except Exception as exc:
        if on_error:
            on_error(f"Unexpected error {host}:{port}", exc)

# ----------------------------------------------------------------------
# Clase pública: PortScanner
# ----------------------------------------------------------------------
class PortScanner:
    """
    Escáner de puertos TCP basado en asyncio.
    Parámetros:
        concurrency (int): número máximo de tareas simultáneas.
        timeout (float): segundos de espera para cada intento de conexión.
        on_open / on_close / on_error: callbacks opcionales.
    """
    def __init__(
        self,
        concurrency: int = 500,
        timeout: float = 3.0,
        on_open: Optional[OnOpenCallback] = None,
        on_close: Optional[OnCloseCallback] = None,
        on_error: Optional[OnErrorCallback] = None
    ):
        self.concurrency = max(1, concurrency)
        self.timeout = timeout
        self.on_open = on_open
        self.on_close = on_close
        self.on_error = on_error
        
        # Estado interno
        self._semaphore = asyncio.Semaphore(self.concurrency)
        self._tasks: List[asyncio.Task] = []
        self._results: List[PortResult] = []

    async def _bounded_probe(self, host: str, port: int) -> None:
        async with self._semaphore:
            def _local_on_open(res: PortResult):
                self._results.append(res)
                if self.on_open:
                    self.on_open(res)

            def _local_on_close(res: PortResult):
                if self.on_close:
                    self.on_close(res)

            await _probe(
                host,
                port,
                self.timeout,
                on_open=_local_on_open,
                on_close=_local_on_close,
                on_error=self.on_error
            )

    async def scan_ports(self, host: str, ports: Iterable[int]) -> List[PortResult]:
        """
        Escanea una lista o rango de puertos en un host de forma asíncrona y controlada.
        """
        self._results.clear()
        tasks = [self._bounded_probe(host, port) for port in ports]
        await asyncio.gather(*tasks)
        return self._results
