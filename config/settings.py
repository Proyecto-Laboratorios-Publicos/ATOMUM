"""
Configuración centralizada y segura de ATOMUM utilizando Pydantic.
Protege credenciales mediante SecretStr y valida variables de entorno.
"""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr, field_validator

class Settings(BaseSettings):
    # Claves sensibles protegidas con SecretStr para evitar exposición en logs
    GROQ_API_KEY: SecretStr = Field(..., description="Clave de API oficial para el motor Groq")
    MODEL_NAME: str = Field(default="llama-3.3-70b-versatile", description="Modelo LLM predeterminado")
    
    # Parámetros operativos del núcleo
    DEBUG_MODE: bool = Field(default=False, description="Activa el modo de registro extendido")
    MAX_TOKENS: int = Field(default=4096, description="Límite máximo de tokens por respuesta")

    @field_validator('MODEL_NAME')
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('El nombre del modelo no puede estar vacío')
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instancia global única de configuración
settings = Settings()
