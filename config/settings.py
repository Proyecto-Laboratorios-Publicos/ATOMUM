"""
Configuración centralizada de ATOMUM utilizando Pydantic.
Valida y gestiona las variables de entorno del sistema de forma segura.
"""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # Configuración de la API y modelo cognitivo
    GROQ_API_KEY: str = Field(..., description="Clave de API oficial para el motor Groq")
    MODEL_NAME: str = Field(default="llama-3.3-70b-versatile", description="Modelo LLM predeterminado")
    
    # Parámetros operativos del núcleo
    DEBUG_MODE: bool = Field(default=False, description="Activa el modo de registro extendido")
    MAX_TOKENS: int = Field(default=4096, description="Límite máximo de tokens por respuesta")

    # Configuración de Pydantic para cargar desde .env si existe
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instancia global única de configuración
settings = Settings()
