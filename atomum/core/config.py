import os
from dataclasses import dataclass

@dataclass
class AtomumConfig:
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    default_model: str = os.getenv("ATOMUM_DEFAULT_MODEL", "openai/gpt-oss-120b")
    environment: str = os.getenv("ATOMUM_ENV", "production")

    def validate(self) -> None:
        if not self.groq_api_key:
            raise ValueError("Falta configurar GROQ_API_KEY en los secretos de Streamlit o variables de entorno.")

settings = AtomumConfig()
