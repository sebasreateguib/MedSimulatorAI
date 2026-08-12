"""
Loop principal de orquestación para MedSimulator AI.
"""
import logging
import yaml
from pathlib import Path
from typing import AsyncGenerator, Any, Dict, List

from medsimulator.agents.router import AgenteRouter
from medsimulator.agents.paciente import AgentePaciente
from medsimulator.agents.especialista import AgenteEspecialista
from medsimulator.agents.tutor import AgenteTutor
from medsimulator.agents.tools import procesar_herramienta
from medsimulator.llm.schemas import EvaluacionClinica

logger = logging.getLogger(__name__)

class Orchestrator:
    """
    Orquestador principal que maneja el ciclo de vida de la sesión
    y enruta los mensajes entre el usuario y los agentes.
    """
    def __init__(self):
        logger.info("Inicializando Orchestrator")
        self.router = AgenteRouter()
        self.paciente = AgentePaciente()
        self.especialista = AgenteEspecialista()
        self.tutor = AgenteTutor()
        self.historial: List[Dict[str, Any]] = []
        self.caso: Dict[str, Any] = {}
        self.sesion_id: str = ""

    async def iniciar_sesion(self, caso_id: str) -> Dict[str, Any]:
        """
        Inicializa una nueva sesión clínica.
        """
        logger.info(f"Iniciando sesión para caso: {caso_id}")
        self.historial = []
        self.sesion_id = f"sesion_{caso_id}"
        
        # Cargar caso desde yaml
        # Asume estructura del proyecto: proyecto_root/config/casos/{caso_id}.yaml
        base_path = Path(__file__).resolve().parent.parent.parent
        ruta_caso = base_path / "config" / "casos" / f"{caso_id}.yaml"
        
        if not ruta_caso.exists():
            logger.error(f"Archivo de caso no encontrado: {ruta_caso}")
            raise FileNotFoundError(f"Caso {caso_id} no encontrado")
            
        with open(ruta_caso, 'r', encoding='utf-8') as f:
            self.caso = yaml.safe_load(f)
            
        # Generar un mensaje de bienvenida de parte del sistema
        paciente_nombre = self.caso.get("paciente", {}).get("nombre", "el paciente")
        mensaje_inicial = f"El paciente {paciente_nombre} ha ingresado a tu consultorio."
        self.historial.append({"role": "system", "content": mensaje_inicial})
        
        return {
            "status": "started", 
            "caso": caso_id,
            "mensaje_inicial": mensaje_inicial,
            "paciente_info": self.caso.get("paciente", {})
        }

    async def procesar_turno(self, entrada_estudiante: str) -> AsyncGenerator[str, None]:
        """
        Procesa un turno enviando la entrada del estudiante al loop de agentes.
        Soporta streaming SSE.
        """
        logger.debug(f"Procesando turno: {entrada_estudiante[:50]}...")
        self.historial.append({"role": "user", "content": entrada_estudiante})
        
        # 1. Enviar a Router para clasificar intención
        intencion = await self.router.clasificar(entrada_estudiante)
        logger.info(f"Intención clasificada: {intencion}")
        
        # 2. Despachar según intención
        respuesta_final = ""
        
        if intencion in ["anamnesis", "otro"]:
            # Hablar con el paciente con streaming
            async for chunk in self.paciente.responder_stream(entrada_estudiante, self.historial, self.caso):
                respuesta_final += chunk
                yield chunk
                
            self.historial.append({"role": "assistant", "content": respuesta_final})
            
        elif intencion in ["laboratorio", "imagen", "receta", "diagnostico"]:
            # Procesar herramientas
            # Idealmente extraeríamos los argumentos de un LLM extractor de herramienta,
            # pero por simplicidad usaremos un mock rápido de argumentos según la entrada
            # En un sistema completo, aquí se llamaría a un modelo con function calling forzado
            # Asumiremos que tenemos un extractor rudimentario (simulado aquí)
            
            herramienta = f"pedir_{intencion}" if intencion in ["laboratorio", "imagen"] else intencion
            
            # Simulamos que un LLM estructuró los argumentos
            argumentos = {}
            if intencion == "laboratorio":
                argumentos = {"pruebas": ["hemograma", "electrolitos"], "justificacion": entrada_estudiante}
            elif intencion == "imagen":
                argumentos = {"tipo_estudio": "ECG", "justificacion": entrada_estudiante}
            elif intencion == "recetar":
                argumentos = {"medicamentos": [entrada_estudiante]}
            elif intencion == "diagnostico":
                argumentos = {"diagnostico_principal": entrada_estudiante}
                
            # Procesar la herramienta
            resultado = procesar_herramienta(herramienta, argumentos, self.caso)
            
            # Registrar evento en tutor
            evento_tutor = {
                "herramienta": herramienta,
                "argumentos": argumentos,
                "resultado": resultado
            }
            self.tutor.registrar_evento(evento_tutor)
            
            # Mostrar resultado al usuario como system u observer
            mensaje_sistema = f"[{herramienta.upper()}]: {resultado.get('mensaje', '')} {resultado.get('resultados', '')}"
            yield mensaje_sistema
            self.historial.append({"role": "system", "content": mensaje_sistema})
            
            # El paciente reacciona
            reaccion = "\n\nPaciente: "
            yield reaccion
            respuesta_final += reaccion
            
            async for chunk in self.paciente.responder_stream(f"El doctor acaba de {herramienta}. ¿Cómo reaccionas?", self.historial, self.caso):
                respuesta_final += chunk
                yield chunk
                
            self.historial.append({"role": "assistant", "content": respuesta_final})
            
        elif intencion == "interconsulta":
            # Llamar al especialista
            # Extraer especialidad rudimentariamente
            especialidad = "cardiologia"
            for esp in AgenteEspecialista.ESPECIALIDADES.keys():
                if esp in entrada_estudiante.lower():
                    especialidad = esp
                    break
                    
            yield f"Consultando al especialista en {especialidad}...\n\n"
            respuesta_esp = await self.especialista.consultar(especialidad, entrada_estudiante, self.caso)
            
            # Stream falso ya que el especialista no usa streaming en su config
            for palabra in respuesta_esp.split():
                chunk = palabra + " "
                respuesta_final += chunk
                yield chunk
                
            self.historial.append({"role": "assistant", "content": f"[Especialista]: {respuesta_final}"})

    async def finalizar_sesion(self) -> EvaluacionClinica:
        """
        Finaliza la sesión actual y solicita la evaluación final al Tutor.
        """
        logger.info("Finalizando sesión")
        evaluacion = await self.tutor.evaluar_final(self.historial, self.caso)
        return evaluacion
