"""
Configuración global de la aplicación usando pydantic-settings.
"""
import yaml
import logging
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """
    Clase de configuración que carga variables de entorno.
    """
    # Claves de API para modelos
    GROQ_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    
    # Base de datos
    DATABASE_URL: str = "postgresql+asyncpg://medsim:medsim_password@localhost/medsimulator"
    
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

    @lru_cache()
    def cargar_config_agentes(self) -> Dict[str, Any]:
        """
        Carga y cachea la configuración de los agentes desde agents.yaml.
        """
        # La ruta base asume que este archivo está en medsimulator/app/
        base_dir = Path(__file__).parent.parent.parent
        agents_path = base_dir / "config" / "agents.yaml"
        
        try:
            with open(agents_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning(f"No se encontró el archivo de configuración de agentes en {agents_path}")
            return {}
        except Exception as e:
            logger.error(f"Error cargando agents.yaml: {e}")
            return {}

# Instancia singleton de la configuración
settings = Settings()
