# security/port_scanner/core.py
"""
Motor asíncrono de escaneo de puertos TCP con soporte para Banner Grabbing.
- Utiliza asyncio + semaphore para limitar la concurrencia.
- Emite callbacks detallados para capturar puertos abiertos, banners y estados.
"""
import asyncio
import socket
from typing import Callable, Iterable, List, Tuple, Optional

# Tipos de callback adaptados para soportar (host, port, is_open, banner)
PortResult = Tuple[str, int, bool]
BannerResult = Tuple[str, int, bool, str]
OnOpenCallback = Callable[[BannerResult], None]
OnCloseCallback = Callable[[PortResult], None]
OnErrorCallback = Callable[[str, Exception], None]

async def _grab_banner(host: str, port: int, timeout: float) -> str:
    """Intenta capturar el banner de bienvenida del servicio abierto de forma segura."""
    banner = ""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        try:
            # Enviar una pequeña directiva a puertos HTTP/HTTPS para forzar respuesta si es necesario
            if port in (80, 8080):
                writer.write(b"HEAD / HTTP/1.0\r\nHost: " + host.encode() + b"\r\n\r\n")
                await writer.drain()
            
            data = await asyncio.wait_for(reader.read(512), timeout=1.0)
            if data:
                banner = data.decode("utf-8", errors="ignore").strip().split("\n")[0]
        except Exception:
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
    except Exception:
        pass
    
    return banner if banner else "Servicio Activo (Sin banner explícito)"

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
    Si está abierto, ejecuta el banner grabbing y emite el callback de apertura.
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        
        # Puerto abierto: cerramos la conexión base temporalmente
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

        # Capturamos el banner de forma asíncrona
        banner = await _grab_banner(host, port, timeout)

        if on_open:
            on_open((host, port, True, banner))

    except asyncio.TimeoutError as exc:
        if on_close:
            on_close((host, port, False))
        if on_error:
            on_error(f"Timeout {host}:{port}", exc)
    except (ConnectionRefusedError, OSError) as exc:
        if on_close:
            on_close((host, port, False))
    except Exception as exc:
        if on_close:
            on_close((host, port, False))
        if on_error:
            on_error(f"Unexpected error {host}:{port}", exc)

class PortScanner:
    """
    Escáner de puertos TCP avanzado basado en asyncio con control de concurrencia.
    """
    def __init__(
        self,
        concurrency: int = 300,
        timeout: float = 2.0,
        on_open: Optional[OnOpenCallback] = None,
        on_close: Optional[OnCloseCallback] = None,
        on_error: Optional[OnErrorCallback] = None
    ):
        self.concurrency = max(1, concurrency)
        self.timeout = timeout
        self.on_open = on_open
        self.on_close = on_close
        self.on_error = on_error
        self._semaphore = asyncio.Semaphore(self.concurrency)
        self._results: List[BannerResult] = []

    async def _bounded_probe(self, host: str, port: int) -> None:
        async with self._semaphore:
            def _local_on_open(res: BannerResult):
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

    async def scan_ports(self, host: str, ports: Iterable[int]) -> List[BannerResult]:
        """
        Ejecuta el escaneo concurrente sobre la lista de puertos indicada.
        """
        self._results.clear()
        tasks = [self._bounded_probe(host, port) for port in ports]
        await asyncio.gather(*tasks)
        return self._results
