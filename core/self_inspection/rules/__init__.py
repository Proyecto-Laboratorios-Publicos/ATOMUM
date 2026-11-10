from pathlib import Path
from importlib import import_module
from pkgutil import iter_modules
from .base import BaseRule

def load_all_rules() -> list[BaseRule]:
    """Descubre e instancia automáticamente todas las reglas dentro del directorio rules/."""
    pkg_name = __name__
    rules = []
    rules_dir = Path(__file__).parent
    
    for _, mod_name, _ in iter_modules([str(rules_dir)]):
        module = import_module(f".{mod_name}", package=pkg_name)
        for obj in vars(module).values():
            if isinstance(obj, type) and issubclass(obj, BaseRule) and obj is not BaseRule:
                rules.append(obj())
                
    return rules
