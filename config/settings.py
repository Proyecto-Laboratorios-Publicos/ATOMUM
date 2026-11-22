"""
Configuración centralizada y segura de ATOMUM utilizando Pydantic.
Permite un inicio degradado seguro si faltan credenciales externas.
"""

from typing import Optional
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Claves sensibles protegidas con SecretStr; opcionales para evitar bloqueos en el arranque
    GROQ_API_KEY: Optional[SecretStr] = Field(
        default=None,
        description="Clave de API oficial para el motor Groq",
    )
    MODEL_NAME: str = Field(
        default="openai/gpt-oss-120b",
        description="Modelo LLM predeterminado",
    )

    # Parámetros operativos del núcleo
    DEBUG_MODE: bool = Field(
        default=False,
        description="Activa el modo de registro extendido",
    )
    MAX_TOKENS: int = Field(
        default=16384,
        gt=0,
        description="Límite máximo de tokens por respuesta",
    )

    @field_validator("GROQ_API_KEY", mode="before")
    @classmethod
    def normalize_empty_api_key(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("MODEL_NAME")
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("El nombre del modelo no puede estar vacío")
        return cleaned

    def get_groq_api_key(self) -> Optional[str]:
        return self.GROQ_API_KEY.get_secret_value() if self.GROQ_API_KEY else None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Instancia global única de configuración
settings = Settings()
