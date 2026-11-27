from typing import List, Optional
from memory.procedural.playbook import Playbook
from memory.procedural.store import ProceduralMemoryStore

class ProceduralMemoryManager:
    """Administrador central para la gestión y recuperación de la memoria procedimental."""

    def __init__(self, store: ProceduralMemoryStore) -> None:
        self.store = store

    def save_playbook(self, playbook: Playbook) -> None:
        """Guarda un playbook en el sistema de almacenamiento."""
        self.store.save_playbook(playbook)

    def get_playbook(self, playbook_id: str) -> Optional[Playbook]:
        """Recupera un playbook por su ID."""
        return self.store.get_playbook(playbook_id)
