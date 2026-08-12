"""
Módulo de agentes para MedSimulator AI.
"""
import logging
from .orchestrator import Orchestrator
from .paciente import AgentePaciente
from .router import AgenteRouter
from .especialista import AgenteEspecialista
from .tutor import AgenteTutor
from .tools import HERRAMIENTAS_CLINICAS, procesar_herramienta

logger = logging.getLogger(__name__)

__all__ = [
    "Orchestrator",
    "AgentePaciente",
    "AgenteRouter",
    "AgenteEspecialista",
    "AgenteTutor",
    "HERRAMIENTAS_CLINICAS",
    "procesar_herramienta"
]
