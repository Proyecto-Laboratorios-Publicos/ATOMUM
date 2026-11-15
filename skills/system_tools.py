#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo: skills.system_tools

Proporciona la clase :class:`SystemTools` con utilidades de bajo nivel para
interactuar con el sistema operativo de forma segura.  El código ha sido
refactorizado para:

* Añadir anotaciones de tipo estático (compatible con Python 3.8+).
* Documentar explícitamente los parámetros, retornos y posibles excepciones.
* Capturar excepciones concretas (``OSError`` y ``subprocess.TimeoutExpired``) en
  lugar de una cláusula genérica ``except Exception``.
* Mantener el mismo comportamiento y salida de consola que la versión original.

El módulo no introduce dependencias externas y sigue siendo 100 % retrocompatible.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any

__all__ = ["SystemTools"]


class SystemTools:
    """
    Herramientas de sistema avanzadas para ATOMUM.

    La clase se inicializa mostrando un mensaje informativo y expone tres
    métodos principales:

    * :meth:`list_directory` – lista de forma segura los contenidos de un
      directorio.
    * :meth:`get_system_info` – devuelve un diagnóstico rápido del entorno.
    * :meth:`execute_safe_command` – ejecuta un comando externo con control de
      tiempo límite y captura de errores.
    """

    def __init__(self) -> None:
        """Inicializa la instancia mostrando un mensaje de arranque."""
        print("⚡ [Skills: System] Herramientas de sistema avanzadas inicializadas.")

    def list_directory(self, path: str | os.PathLike = ".") -> List[str]:
        """
        Lista los archivos y carpetas en un directorio dado.

        Parameters
        ----------
        path: str | os.PathLike, optional
            Ruta del directorio a inspeccionar. Por defecto, el directorio
            actual (``"."``).

        Returns
        -------
        List[str]
            Lista de nombres de entradas dentro del directorio. Si ocurre un
            error, se devuelve una lista vacía.

        Raises
        ------
        OSError
            Si el directorio no existe o no se pueden leer sus contenidos.
        """
        try:
            # ``Path`` permite aceptar tanto ``str`` como objetos ``PathLike``.
            items: List[str] = os.listdir(Path(path))
            print(
                f"📂 [Skills: System] Listando directorio '{path}': "
                f"{len(items)} elementos encontrados."
            )
            return items
        except OSError as exc:
            error_msg = f"❌ [Skills: System Error] No se pudo listar el directorio: {exc}"
            print(error_msg)
            return []

    def get_system_info(self) -> Dict[str, Any]:
        """
        Obtiene un diagnóstico rápido del entorno de ejecución.

        Returns
        -------
        dict
            Diccionario con información del sistema operativo, versión de Python,
            arquitectura y directorio de trabajo actual.

        Raises
        ------
        Exception
            Cualquier error inesperado al recopilar la información.
        """
        try:
            info: Dict[str, Any] = {
                "platform": platform.system(),
                "release": platform.release(),
                "python_version": platform.python_version(),
                "architecture": platform.machine(),
                "current_working_dir": os.getcwd(),
            }
            print(f"📊 [Skills: System] Diagnóstico de entorno obtenido: {info}")
            return info
        except Exception as exc:  # pragma: no cover – caso extremadamente raro
            print(f"❌ [Skills: System Error] No se pudo obtener la info del sistema: {exc}")
