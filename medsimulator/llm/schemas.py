"""
Modelos Pydantic compartidos para el proyecto MedSimulator AI.
"""
import logging
from typing import List, Optional, Literal, Any, Dict
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class EvaluacionClinica(BaseModel):
    """Esquema para la evaluación clínica del estudiante."""
    puntaje_total: int = Field(..., ge=0, le=100, description="Puntaje total sobre 100")
    razonamiento_diagnostico: str = Field(..., description="Evaluación del razonamiento diagnóstico")
    costo_efectividad: str = Field(..., description="Análisis del costo-efectividad de las decisiones")
    pruebas_innecesarias: List[str] = Field(default_factory=list, description="Lista de pruebas solicitadas innecesariamente")
    errores_criticos: List[str] = Field(default_factory=list, description="Lista de errores críticos cometidos")
    retroalimentacion: str = Field(..., description="Retroalimentación general para el estudiante")

class FlashcardGenerada(BaseModel):
    """Una tarjeta de repaso derivada del material del usuario."""
    anverso: str = Field(..., description="Pregunta o concepto a recordar")
    reverso: str = Field(..., description="Respuesta completa pero breve")
    fuente: Optional[str] = Field(None, description="Documento del que sale la tarjeta")
    pagina: Optional[int] = Field(None, description="Página del documento, si aplica")

class MazoGenerado(BaseModel):
    """Respuesta estructurada del generador de flashcards."""
    titulo: str = Field(..., description="Título breve del mazo")
    flashcards: List[FlashcardGenerada] = Field(default_factory=list)

class AfirmacionValidada(BaseModel):
    """Esquema para la validación de afirmaciones clínicas."""
    afirmacion: str
    chunk_id: str
    cita_literal: str
    veredicto: Literal["correcto", "incorrecto", "no_verificable"]

class MensajeChat(BaseModel):
    """Modelo estándar para mensajes de chat."""
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None

class RespuestaAgente(BaseModel):
    """Modelo para la respuesta generada por cualquier agente."""
    agente: str = Field(..., description="Nombre del agente que responde")
    contenido: str = Field(..., description="Contenido de la respuesta")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="Llamadas a herramientas si aplica")
    citations: Optional[List[str]] = Field(None, description="Citas a documentos de referencia")

class ConfigAgente(BaseModel):
    """Configuración de un agente definida en agents.yaml."""
    provider: str
    model: str
    temperature: Optional[float] = 0.7
    effort: Optional[str] = None
    citations: Optional[bool] = False

class CasoClinico(BaseModel):
    """Estructura de un caso clínico cargado desde YAML."""
    id: str
    nombre: str
    paciente: Dict[str, Any]
    historia_oculta: str
    sintomas: List[str]
    estado_emocional: str
    laboratorios: Dict[str, Any]
    imagenes: Dict[str, Any]
    diagnostico_correcto: str
    criterios_diagnosticos: List[str]
    plan_tratamiento: List[str]
