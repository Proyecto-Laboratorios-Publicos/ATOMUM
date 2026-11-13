# -*- coding: utf-8 -*-
"""
core/security_analyzer.py
-------------------------

Módulo central de ATOMUM para análisis estático, generación de hashes y auditoría de logs.
Diseñado para ser invocado desde CI (GitHub Actions, GitLab CI) o como CLI local.

Requisitos (pip):
    pip install bandit pylint mypy pytest pytest-cov python-dotenv loguru tqdm

Uso rápido:
    python -m core.security_analyzer --path ./my_project
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

from loguru import logger
from tqdm import tqdm

# --------------------------------------------------------------------------- #
# CONFIGURACIÓN GLOBAL
# --------------------------------------------------------------------------- #
HASH_FILE = Path("hashes.txt")
LOG_FILE = Path("logs/security_analyzer.log.jsonl")
ALLOWED_EXT = {".py", ".pyi"}          # extensiones a analizar
EXCLUDE_DIRS = {"venv", "__pycache__", ".git", "build", "dist"}

# --------------------------------------------------------------------------- #
# UTILIDADES DE LOGGING
# --------------------------------------------------------------------------- #
def _setup_logger() -> None:
    """Inicializa logger en formato JSON Lines."""
    logger.remove()
    logger.add(
        LOG_FILE,
        format="{time:ISO8601} | {level} | {message}",
        serialize=True,
        level="INFO",
        rotation="10 MB",
        retention="7 days",
        enqueue=True,
    )
    logger.info("Security Analyzer started", pid=os.getpid())

# --------------------------------------------------------------------------- #
# HASHING DE ARCHIVOS
# --------------------------------------------------------------------------- #
def compute_sha256(file_path: Path) -> str:
    """Devuelve el hash SHA‑256 del contenido del archivo."""
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def update_hash_file(root: Path) -> None:
    """Reescribe hashes.txt con los hashes actuales de todos los archivos .py."""
    lines = []
    for file_path in _iter_python_files(root):
        sha = compute_sha256(file_path)
        rel = file_path.relative_to(root)
        lines.append(f"{sha}  {rel}\n")
    HASH_FILE.write_text("".join(lines), encoding="utf-8")
    logger.info("Hash file updated", count=len(lines))


def verify_hashes(root: Path) -> Tuple[bool, List[str]]:
    """Compara hashes.txt con el estado actual del árbol.
    Devuelve (todo_ok, lista_de_errores)."""
    if not HASH_FILE.is_file():
        logger.warning("Hash file missing, generating fresh one")
        update_hash_file(root)
        return True, []

    expected = {}
    for line in HASH_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        sha, rel = line.split(maxsplit=1)
        expected[Path(rel)] = sha

    errors = []
    for file_path in _iter_python_files(root):
        rel = file_path.relative_to(root)
        current_sha = compute_sha256(file_path)
        if rel not in expected:
            errors.append(f"Nuevo archivo detectado: {rel}")
        elif expected[rel] != current_sha:
            errors.append(f"Hash mismatch: {rel}")

    # Archivos eliminados
    for rel in set(expected) - {p.relative_to(root) for p in _iter_python_files(root)}:
        errors.append(f"Archivo eliminado: {rel}")

    ok = not errors
    if ok:
        logger.info("Hash verification passed")
    else:
        logger.error("Hash verification failed", errors=errors)
    return ok, errors


def _iter_python_files(root: Path):
    """Generador de Path para archivos .py bajo root, excluyendo EXCLUDE_DIRS."""
    for dirpath, dirnames, filenames in os.walk(root):
        # excluir directorios
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fname in filenames:
            if Path(fname).suffix in ALLOWED_EXT:
                yield Path(dirpath) / fname


# --------------------------------------------------------------------------- #
# EJECUCIÓN DE HERRAMIENTAS ESTÁTICAS
# --------------------------------------------------------------------------- #
def _run_tool(command: List[str]) -> Tuple[int, str]:
    """Ejecuta una herramienta externa y devuelve (returncode, stdout+stderr)."""
    proc = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout


def run_bandit(target: Path) -> Tuple[int, str]:
    """Ejecuta bandit (vulnerabilidades de seguridad)."""
    cmd = ["bandit", "-r", str(target), "-ll", "-f", "json"]
    return _run_tool(cmd)


def run_pylint(target: Path) -> Tuple[int, str]:
    """Ejecuta pylint con perfil de seguridad."""
    cmd = [
        "pylint",
        str(target),
        "--disable=all",
        "--enable=bad-builtin,eval-used,exec-used,global-statement,unused-import",
        "-f", "json",
    ]
    return _run_tool(cmd)


def run_mypy(target: Path) -> Tuple[int, str]:
    """Ejecuta mypy en modo estricto."""
    cmd = ["mypy", str(target), "--strict", "--show-error-codes", "--pretty"]
    return _run_tool(cmd)


def aggregate_results(bandit_out: str, pylint_out: str, mypy_out: str) -> dict:
    """Normaliza la salida de las tres herramientas en un único dict."""
    results = {
        "bandit": json.loads(bandit_out) if bandit_out else {},
        "pylint": json.loads(pylint_out) if pylint_out else [],
        "mypy": mypy_out.strip().splitlines() if mypy_out else [],
    }
    return results


# --------------------------------------------------------------------------- #
# INFORME TÉCNICO (JSON → .docx)
# --------------------------------------------------------------------------- #
def generate_report(results: dict, output_path: Path) -> None:
    """
    Crea un informe .docx estructurado usando python‑docx.
    El informe contiene:
        • Resumen de Calidad
        • Hallazgos de Código (por herramienta)
        • Recomendaciones de Mitigación
    """
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    doc.add_heading("Informe de Auditoría de Seguridad – ATOMUM", level=0)

    # 1. Resumen
    doc.add_heading("1. Resumen de Calidad", level=1)
    total_findings = (
        len(results["bandit"].get("results", []))
        + len(results["pylint"])
        + len(results["mypy"])
    )
    doc.add_paragraph(f"Total de hallazgos críticos: {total_findings}")

    # 2. Hallazgos por herramienta
    doc.add_heading("2. Hallazgos de Código", level=1)

    # Bandit
    doc.add_heading("2.1 Bandit (Vulnerabilidades de Seguridad)", level=2)
    if results["bandit"].get("results"):
        for item in results["bandit"]["results"]:
            p = doc.add_paragraph(style="List Bullet")
            p.add_run(f"{item['filename']}:{item['line_number']} – ")
            p.add_run(item["test_name"]).bold = True
            p.add_run(f" – {item['issue_text']}")
    else:
        doc.add_paragraph("No se detectaron vulnerabilidades con Bandit.")

    # Pylint
    doc.add_heading("2.2 Pylint (Malas prácticas)", level=2)
    if results["pylint"]:
        for entry in results["pylint"]:
            p = doc.add_paragraph(style="List Bullet")
            p.add_run(f"{entry['path']}:{entry['line']} – ")
            p.add_run(entry["symbol"]).bold = True
            p.add_run(f" – {entry['message']}")
    else:
        doc.add_paragraph("Pylint no reportó problemas de seguridad.")

    # MyPy
    doc.add_heading("2.3 MyPy (Tipado estático)", level=2)
    if results["mypy"]:
        for line in results["mypy"]:
            doc.add_paragraph(line, style="List Bullet")
    else:
        doc.add_paragraph("MyPy no encontró errores de tipado.")

    # 3. Recomendaciones
    doc.add_heading("3. Recomendaciones de Mitigación", level=1)
    recs = [
        "Aplicar validación estricta a todas las entradas externas (OWASP‑A1).",
        "Reemplazar cualquier uso de `eval`/`exec` por funciones seguras o DSL controladas.",
        "Actualizar dependencias a versiones sin CVE (ejecutar `pip-audit`).",
        "Implementar manejo de errores específico; evitar `except Exception` genérico.",
        "Revisar los logs para asegurarse de que no se filtren datos sensibles.",
    ]
    for r in recs:
        doc.add_paragraph(r, style="List Number")

    # Guardar
    doc.save(output_path)
    logger.info("Report generated", path=str(output_path))


# --------------------------------------------------------------------------- #
# INTERFAZ DE LÍNEA DE COMANDOS
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ATOMUM – Analizador estático de código Python"
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("."),
        help="Directorio raíz del proyecto a analizar",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("security_audit_report.docx"),
        help="Archivo de salida del informe (.docx)",
    )
    parser.add_argument(
        "--no‑hash",
        action="store_true",
        help="Desactivar verificación/actualización de hashes (solo para pruebas rápidas)",
    )
    return parser.parse_args()


def main() -> int:
    _setup_logger()
    args = parse_args()
    root = args.path.resolve()

    # 1️⃣ Verificación de integridad (hashes)
    if not args.no_hash:
        ok, errors = verify_hashes(root)
        if not ok:
            logger.error("Hash verification failed – aborting analysis")
            for e in errors:
                logger.error(e)
            return 1
        else:
            logger.info("Hash verification OK")

    # 2️⃣ Análisis estático
    logger.info("Running Bandit")
    rc_bandit, out_bandit = run_bandit(root)

    logger.info("Running Pylint")
    rc_pylint, out_pylint = run_pylint(root)

    logger.info("Running MyPy")
    rc_mypy, out_mypy = run_mypy(root)

    # 3️⃣ Agregación de resultados
    results = aggregate_results(out_bandit, out_pylint, out_mypy)

    # 4️⃣ Generación de informe
    generate_report(results, args.report)

    # 5️⃣ Actualizar hashes (post‑análisis)
    if not args.no_hash:
        update_hash_file(root)

    logger.info("Security analysis completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
