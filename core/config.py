import os
from dataclasses import dataclass

@dataclass
class AtomumConfig:
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    default_model: str = os.getenv("ATOMUM_DEFAULT_MODEL", "llama3-70b-8192")
    environment: str = os.getenv("ATOMUM_ENV", "production")

    def validate(self) -> None:
        if not self.groq_api_key:
            raise ValueError("Falta configurar GROQ_API_KEY en los secretos de Streamlit o variables de entorno.")

settings = AtomumConfig()
