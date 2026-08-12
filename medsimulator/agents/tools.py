"""
Definiciones de herramientas clínicas (Function Calling).
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

HERRAMIENTAS_CLINICAS = [
    {
        "type": "function",
        "function": {
            "name": "pedir_laboratorio",
            "description": "Solicitar pruebas de laboratorio (hemograma, química, etc).",
            "parameters": {
                "type": "object",
                "properties": {
                    "pruebas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de pruebas de laboratorio a solicitar."
                    },
                    "justificacion": {
                        "type": "string",
                        "description": "Razonamiento clínico para pedir estas pruebas."
                    }
                },
                "required": ["pruebas", "justificacion"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pedir_imagen",
            "description": "Solicitar estudios de imagen (Rx, TAC, RM, ECG, etc).",
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo_estudio": {
                        "type": "string",
                        "description": "Tipo de imagen o estudio (ej. Radiografía de tórax, ECG)."
                    },
                    "justificacion": {
                        "type": "string",
                        "description": "Por qué se necesita esta imagen o estudio."
                    }
                },
                "required": ["tipo_estudio", "justificacion"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recetar",
            "description": "Prescribir medicamentos o tratamientos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "medicamentos": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de medicamentos y dosis."
                    }
                },
                "required": ["medicamentos"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "diagnosticar",
            "description": "Establecer el diagnóstico final.",
            "parameters": {
                "type": "object",
                "properties": {
                    "diagnostico_principal": {
                        "type": "string"
                    },
                    "diagnosticos_diferenciales": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["diagnostico_principal"]
            }
        }
    }
]

def procesar_herramienta(nombre: str, argumentos: Dict[str, Any], caso: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ejecuta la simulación de la herramienta clínica solicitada.
    
    Args:
        nombre: Nombre de la herramienta (ej. 'pedir_laboratorio').
        argumentos: Argumentos provistos por el LLM.
        caso: Diccionario con la información del caso clínico.
        
    Returns:
        Resultados de la herramienta (simulados).
    """
    logger.info(f"Ejecutando herramienta clínica: {nombre}")
    
    if nombre == "pedir_laboratorio":
        resultados_reales = caso.get("resultados_laboratorio", caso.get("laboratorios", {}))
        pruebas_solicitadas = argumentos.get("pruebas", [])
        return {
            "status": "success",
            "mensaje": "Resultados de laboratorio obtenidos exitosamente.",
            "resultados": resultados_reales,
            "pruebas_solicitadas": pruebas_solicitadas
        }
        
    elif nombre == "pedir_imagen":
        # Se asume que ECG puede estar en hallazgos_ecg o dentro de imagenes
        hallazgos = caso.get("hallazgos_ecg", caso.get("imagenes", {}))
        tipo_estudio = argumentos.get("tipo_estudio", "estudio de imagen")
        return {
            "status": "success",
            "mensaje": f"Hallazgos para {tipo_estudio} obtenidos.",
            "resultados": hallazgos
        }
        
    elif nombre == "recetar":
        medicamentos = argumentos.get("medicamentos", [])
        return {
            "status": "success",
            "mensaje": "Se han registrado los medicamentos recetados.",
            "medicamentos_recetados": medicamentos
        }
        
    elif nombre == "diagnosticar":
        diag_principal = argumentos.get("diagnostico_principal", "")
        return {
            "status": "success",
            "mensaje": f"Diagnóstico principal '{diag_principal}' registrado.",
            "diagnostico": diag_principal
        }
        
    else:
        return {
            "status": "error",
            "mensaje": f"Herramienta {nombre} no soportada.",
            "resultados": {}
        }
