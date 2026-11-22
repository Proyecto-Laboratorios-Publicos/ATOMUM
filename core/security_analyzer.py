# -*- coding: utf-8 -*-
"""
core/security_analyzer.py
-------------------------
Módulo central de ATOMUM para análisis estático, generación de hashes y auditoría de logs.
Diseñado para ser invocado desde CI (GitHub Actions, GitLab CI) o como CLI local.

Requisitos (pip):
    pip install bandit pylint mypy python-docx loguru

Uso rápido:
    python -m core.security_analyzer --path ./my_project
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterator

from loguru import logger

# --------------------------------------------------------------------------- #
# CONFIGURACIÓN GLOBAL
# --------------------------------------------------------------------------- #
DEFAULT_HASH_FILENAME = "hashes.txt"
DEFAULT_LOG_REL_PATH = Path("logs/security_analyzer.log.jsonl")
ALLOWED_EXT: frozenset[str] = frozenset({".py", ".pyi"})
EXCLUDE_DIRS: frozenset[str] = frozenset(
    {"venv", ".venv", "__pycache__", ".git", "build", "dist", ".mypy_cache"}
)


# --------------------------------------------------------------------------- #
# UTILIDADES DE LOGGING
# --------------------------------------------------------------------------- #
def _setup_logger(log_file: Path) -> None:
    """Inicializa logger en formato JSON Lines asegurando la existencia del directorio."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(
        log_file,
        format="{time:ISO8601} | {level} | {message}",
        serialize=True,
        level="INFO",
        rotation="10 MB",
        retention="7 days",
        enqueue=True,
    )
    logger.info("Security Analyzer started", pid=os.getpid(), log_file=str(log_file))


# --------------------------------------------------------------------------- #
# HASHING DE ARCHIVOS
# --------------------------------------------------------------------------- #
def _iter_python_files(root: Path) -> Iterator[Path]:
    """Generador ordenado de archivos Python bajo root, excluyendo EXCLUDE_DIRS."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDE_DIRS)
        for fname in sorted(filenames):
            if Path(fname).suffix in ALLOWED_EXT:
                yield Path(dirpath) / fname


def compute_sha256(file_path: Path) -> str:
    """Devuelve el hash SHA-256 del contenido del archivo."""
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def update_hash_file(root: Path, hash_file: Path) -> None:
    """Reescribe el archivo de hashes con los SHA-256 actuales de todos los archivos Python."""
    hash_file.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for file_path in _iter_python_files(root):
        sha = compute_sha256(file_path)
        rel = file_path.relative_to(root).as_posix()
        lines.append(f"{sha}  {rel}\n")
    hash_file.write_text("".join(lines), encoding="utf-8")
    logger.info("Hash file updated", count=len(lines), path=str(hash_file))


def verify_hashes(
    root: Path,
    hash_file: Path,
    *,
    strict_missing: bool = False,
) -> tuple[bool, list[str]]:
    """Compara el archivo de hashes con el estado actual del árbol."""
    if not hash_file.is_file():
        if strict_missing:
            msg = f"Archivo de integridad no encontrado en modo estricto: {hash_file}"
            logger.error(msg)
            return False, [msg]
        logger.warning("Hash file missing, generating fresh baseline", path=str(hash_file))
        update_hash_file(root, hash_file)
        return True, []

    expected: dict[str, str] = {}
    for line in hash_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            sha, rel = parts
            expected[Path(rel).as_posix()] = sha

    errors: list[str] = []
    current_files: set[str] = set()

    for file_path in _iter_python_files(root):
        rel = file_path.relative_to(root).as_posix()
        current_files.add(rel)
        current_sha = compute_sha256(file_path)
        if rel not in expected:
            errors.append(f"Nuevo archivo detectado: {rel}")
        elif expected[rel] != current_sha:
            errors.append(f"Hash mismatch: {rel}")

    for rel in sorted(set(expected) - current_files):
        errors.append(f"Archivo eliminado: {rel}")

    ok = not errors
    if ok:
        logger.info("Hash verification passed")
    else:
        logger.error("Hash verification failed", errors=errors)
    return ok, errors


# --------------------------------------------------------------------------- #
# EJECUCIÓN DE HERRAMIENTAS ESTÁTICAS
# --------------------------------------------------------------------------- #
def _run_tool(command: list[str]) -> tuple[int, str]:
    """Ejecuta una herramienta externa de forma segura y devuelve (returncode, output)."""
    try:
        proc = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        return proc.returncode, proc.stdout
    except FileNotFoundError:
        logger.warning("Herramienta no instalada en el entorno", tool=command[0])
        return 127, ""


def _parse_json_output(raw_output: str, default: Any, tool_name: str) -> Any:
    """Extrae y parsea JSON de la salida de una herramienta tolerando ruido previo/posterior."""
    text = raw_output.strip()
    if not text:
        return default

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start_obj = text.find("{")
        start_arr = text.find("[")
        candidates = [idx for idx in (start_obj, start_arr) if idx != -1]
        if candidates:
            start = min(candidates)
            end_obj = text.rfind("}")
            end_arr = text.rfind("]")
            end = max(end_obj, end_arr)
            if end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass

    logger.warning("No se pudo parsear salida JSON", tool=tool_name)
    return default


def run_bandit(target: Path) -> tuple[int, str]:
    """Ejecuta bandit (vulnerabilidades de seguridad de severidad media/alta)."""
    cmd = ["bandit", "-r", str(target), "-ll", "-f", "json"]
    return _run_tool(cmd)


def run_pylint(target: Path) -> tuple[int, str]:
    """Ejecuta pylint con perfil enfocado en seguridad e higiene."""
    cmd = [
        "pylint",
        str(target),
        "--disable=all",
