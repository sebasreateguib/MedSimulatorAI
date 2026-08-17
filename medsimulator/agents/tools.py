"""
Definiciones de herramientas clínicas (Function Calling).
"""
import logging
import unicodedata
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Sinónimos con los que un estudiante puede nombrar cada estudio. La clave es el
# nombre canónico que se busca en el caso; el orden importa poco, pero las
# entradas más específicas ("radiografia de torax") tienen que estar antes que
# las genéricas ("radiografia") para que gane la más precisa.
SINONIMOS_ESTUDIO: Dict[str, list[str]] = {
    "ecg": ["ecg", "electrocardiograma", "electro", "ekg", "12 derivaciones"],
    "radiografia_torax": [
        "radiografia de torax", "rx de torax", "rx torax", "placa de torax",
        "radiografia toracica", "telerradiografia", "radiografia", "rx",
    ],
    "tac_torax": ["tac de torax", "tomografia de torax", "angiotac", "tac", "tomografia"],
    "ecocardiograma": ["ecocardiograma", "ecocardio", "eco cardiaco", "ecografia cardiaca"],
    "ecografia_abdominal": ["ecografia abdominal", "ecografia de abdomen", "ecografia"],
    "resonancia": ["resonancia", "rm", "rmn"],
}


def _normalizar(texto: str) -> str:
    """Minúsculas y sin tildes: 'Radiografía' y 'radiografia' son lo mismo."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.lower().split())


def identificar_estudio(texto: str) -> Optional[str]:
    """
    Nombre canónico del estudio nombrado en el texto, o None si no reconoce
    ninguno. Se usa tanto para leer lo que pide el estudiante como para indexar
    lo que declara el caso.
    """
    plano = _normalizar(texto)
    mejor: Optional[str] = None
    largo_mejor = 0

    for canonico, alias in SINONIMOS_ESTUDIO.items():
        for termino in alias:
            # Gana el alias más largo que aparezca: "radiografia de torax" tiene
            # que vencer a "radiografia" cuando ambos están en la frase.
            if termino in plano and len(termino) > largo_mejor:
                mejor, largo_mejor = canonico, len(termino)

    return mejor


# Cómo se muestra cada estudio en la transcripción.
NOMBRE_LEGIBLE: Dict[str, str] = {
    "ecg": "ECG de 12 derivaciones",
    "radiografia_torax": "Radiografía de tórax",
    "tac_torax": "TAC de tórax",
    "ecocardiograma": "Ecocardiograma",
    "ecografia_abdominal": "Ecografía abdominal",
    "resonancia": "Resonancia magnética",
}


def nombre_estudio(texto: str) -> str:
    """
    Nombre presentable del estudio que pide el estudiante. Si no se reconoce
    ninguno conocido, se conserva lo que escribió: inventarle un nombre sería
    peor que mostrar el suyo.
    """
    estudio = identificar_estudio(texto)
    if estudio:
        return NOMBRE_LEGIBLE.get(estudio, estudio.replace("_", " "))

    limpio = texto.strip().rstrip(".")
    return limpio if 0 < len(limpio) <= 80 else "Estudio solicitado"


def identificar_laboratorios(texto: str, disponibles: Dict[str, Any]) -> list[str]:
    """
    Qué análisis nombró el estudiante, entre los que el caso tiene cargados.

    Un pedido genérico ("solicito laboratorio") devuelve la lista vacía, y el
    llamador decide entregar el panel completo. Lo que no puede pasar es que se
    registren pruebas que el estudiante nunca pidió: el tutor puntúa
    costo-efectividad con esa lista.
    """
    plano = _normalizar(texto)
    pedidas = []

    for clave in disponibles:
        etiqueta = _normalizar(str(clave)).replace("_", " ")
        # Se compara palabra a palabra: "perfil tiroideo" matchea con "tiroideo"
        # y "hemograma completo" con "hemograma".
        if etiqueta in plano or any(p in plano for p in etiqueta.split() if len(p) > 4):
            pedidas.append(str(clave))

    return pedidas


def _hallazgos_del_caso(caso: Dict[str, Any], estudio: Optional[str]) -> Optional[str]:
    """
    Busca en el caso los hallazgos del estudio pedido.

    Acepta las tres formas en que un YAML puede declararlos: el bloque
    `estudios:`, el viejo `imagenes:` y el campo suelto `hallazgos_ecg`.
    """
    fuentes: Dict[str, Any] = {}
    fuentes.update(caso.get("imagenes") or {})
    fuentes.update(caso.get("estudios") or {})

    if caso.get("hallazgos_ecg"):
        fuentes.setdefault("ecg", caso["hallazgos_ecg"])

    if not estudio:
        return None

    for clave, valor in fuentes.items():
        if identificar_estudio(str(clave)) == estudio or _normalizar(str(clave)) == estudio:
            return str(valor)

    return None

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
        disponibles = caso.get("resultados_laboratorio", caso.get("laboratorios", {})) or {}
        pedidas = argumentos.get("pruebas", [])

        # Se entrega lo que se pidió, no todo lo que el caso tiene: un panel
        # completo regalado por pedir un hemograma le saca sentido a la
        # evaluación de costo-efectividad. Sin pedido explícito va todo.
        if pedidas:
            resultados = {k: v for k, v in disponibles.items() if k in pedidas}
            faltantes = [p for p in pedidas if p not in disponibles]
        else:
            resultados = disponibles
            faltantes = []

        return {
            "status": "success",
            "mensaje": "Resultados de laboratorio obtenidos.",
            "resultados": resultados,
            "pruebas_solicitadas": pedidas or list(disponibles),
            "sin_resultado": faltantes,
        }
        
    elif nombre == "pedir_imagen":
        tipo_estudio = argumentos.get("tipo_estudio", "estudio de imagen")
        estudio = identificar_estudio(tipo_estudio)
        hallazgos = _hallazgos_del_caso(caso, estudio)

        if hallazgos is None:
            # Antes se devolvían los hallazgos del ECG para cualquier pedido: se
            # informaba "Hallazgos para Radiografía de tórax" con el trazado del
            # electro. Un estudio que el caso no define se informa como tal, y el
            # tutor lo evalúa en costo-efectividad como lo que fue: un pedido sin
            # rendimiento diagnóstico.
            logger.info(f"El caso no declara hallazgos para '{tipo_estudio}'.")
            return {
                "status": "sin_hallazgos",
                "mensaje": f"{tipo_estudio}: sin alteraciones relevantes para este caso.",
                "resultados": "",
                "tipo_estudio": tipo_estudio,
            }

        return {
            "status": "success",
            "mensaje": f"{tipo_estudio}: resultado disponible.",
            "resultados": hallazgos,
            "tipo_estudio": tipo_estudio,
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
