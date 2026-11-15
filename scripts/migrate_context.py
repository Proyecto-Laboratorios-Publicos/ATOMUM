import asyncio
import json
from pathlib import Path
from atomum.context.service import ContextService
from atomum.core.logger import get_logger

logger = get_logger("atomum.migration")

async def migrate_legacy_memory(legacy_dir: str = "memory") -> None:
    """Migra registros JSON desde el directorio legado hacia ContextService."""
    source_path = Path(legacy_dir)
    if not source_path.exists() or not source_path.is_dir():
        logger.warning(f"Directorio legado '{legacy_dir}' no encontrado. Nada que migrar.")
        return

    context_service = ContextService()
    migrated_count = 0

    for json_file in source_path.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            key = f"legacy:{json_file.stem}"
            await context_service.set(key, data)
            migrated_count += 1
            logger.info(f"Migrado correctamente: {json_file.name} -> {key}")
        except Exception as e:
            logger.error(f"Error migrando {json_file.name}: {e}")

    logger.info(f"Migración finalizada. Total de registros transferidos: {migrated_count}")

if __name__ == "__main__":
    asyncio.run(migrate_legacy_memory())
