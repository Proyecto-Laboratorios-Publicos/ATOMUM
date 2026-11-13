#!/usr/bin/env python3
"""
security_runner.py
------------------
Orquesta el flujo completo:
1️⃣ Ejecuta core.security_analyzer
2️⃣ Procesa el JSON con core.engine
3️⃣ Exporta a Word con utils.exporter
"""

import subprocess
import sys
import pathlib
import json
import logging
from datetime import datetime

# Añadir al PYTHONPATH el directorio raíz (para imports relativos)
repo_root = pathlib.Path(__file__).resolve().parents[1]
sys.path.append(str(repo_root))

from core.engine import process_security_report
from utils.exporter import export_security_report_to_word

# ----------------------------------------------------------------------
# Configuración de logging
# ----------------------------------------------------------------------
log = logging.getLogger("security_runner")
log.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(message)s", "%Y-%m-%d %H:%M:%S"
)
handler.setFormatter(formatter)
log.addHandler(handler)

# ----------------------------------------------------------------------
# Constantes
# ----------------------------------------------------------------------
REPORT_JSON = repo_root / "security_report.json"
REPORT_DOCX = repo_root / "reports" / f"security_report_{datetime.now():%Y%m%d_%H%M%S}.docx"
ANALYZER_CMD = [
    sys.executable,                     # usa el mismo intérprete que ejecuta este script
    "-m", "core.security_analyzer",
    "--path", ".",
    "--format", "json",
    "--output", str(REPORT_JSON),
]

# ----------------------------------------------------------------------
def run_analyzer() -> pathlib.Path:
    """Ejecuta el módulo core.security_analyzer y devuelve la ruta del JSON."""
    log.info("Iniciando escaneo de seguridad con core.security_analyzer …")
    try:
        subprocess.run(ANALYZER_CMD, check=True, cwd=repo_root)
    except subprocess.CalledProcessError as exc:
        log.error(f"Fallo al ejecutar security_analyzer: {exc}")
        sys.exit(1)

    if not REPORT_JSON.is_file():
        log.error(f"El archivo de salida esperado no se encontró: {REPORT_JSON}")
        sys.exit(1)

    log.info(f"Escaneo completado → {REPORT_JSON}")
    return REPORT_JSON


# ----------------------------------------------------------------------
def main() -> None:
    # 1️⃣ Ejecutar el escáner
    json_path = run_analyzer()

    # 2️⃣ Cargar y procesar resultados
    with json_path.open("r", encoding="utf-8") as f:
        report_data = json.load(f)

    # 2️⃣→3️⃣ Procesar con el motor cognitivo y obtener una lista de alertas
    alerts = process_security_report(report_data)

    # 3️⃣ Exportar a Word
    REPORT_DOCX.parent.mkdir(parents=True, exist_ok=True)
    export_security_report_to_word(report_data, alerts, REPORT_DOCX)

    log.info(f"Informe final generado → {REPORT_DOCX}")

    # Salida de consola resumida
    if alerts:
        log.warning(f"Se detectaron {len(alerts)} vulnerabilidades críticas/alto riesgo.")
        for a in alerts:
            log.warning(f"- [{a['severity']}] {a['id']}: {a['title']}")
    else:
        log.info("No se encontraron vulnerabilidades críticas o de alto riesgo.")


if __name__ == "__main__":
    main()
