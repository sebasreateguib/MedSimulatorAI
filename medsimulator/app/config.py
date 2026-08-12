"""
Configuración global de la aplicación usando pydantic-settings.
"""
import yaml
import logging
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Caché a nivel de módulo. No se usa @lru_cache sobre el método porque
# decorar un método hace que la caché intente hashear `self`, y una instancia
# de BaseSettings no es hasheable (TypeError en la primera llamada).
_config_agentes_cache: Optional[Dict[str, Any]] = None

class Settings(BaseSettings):
    """
    Clase de configuración que carga variables de entorno.
    """
    # Claves de API para modelos
    GROQ_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    
    # Base de datos
    DATABASE_URL: str

    # Autenticación. JWT_SECRET_KEY no tiene default a propósito: un default
    # en el código terminaría firmando tokens en producción sin que nadie lo note.
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12  # 12 horas

    # Orígenes autorizados a llamar la API desde el navegador, separados por coma.
    # Por defecto solo el dev server de Vite.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins_lista(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # Langfuse (Observabilidad)
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        case_sensitive=True,
        extra="ignore"
    )

    def cargar_config_agentes(self) -> Dict[str, Any]:
        """
        Carga y cachea la configuración de los agentes desde agents.yaml.
        """
        global _config_agentes_cache
        if _config_agentes_cache is not None:
            return _config_agentes_cache

        # La ruta base asume que este archivo está en medsimulator/app/
        base_dir = Path(__file__).parent.parent.parent
        agents_path = base_dir / "config" / "agents.yaml"

        try:
            with open(agents_path, "r", encoding="utf-8") as f:
                _config_agentes_cache = yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning(f"No se encontró el archivo de configuración de agentes en {agents_path}")
            _config_agentes_cache = {}
        except Exception as e:
            logger.error(f"Error cargando agents.yaml: {e}")
            _config_agentes_cache = {}

        return _config_agentes_cache

# Instancia singleton de la configuración
settings = Settings()
