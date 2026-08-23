"""
Módulo para la extracción de información de fármacos e interacciones desde openFDA.
"""

import logging
import httpx
from typing import List, Dict, Any, Optional

from medsimulator.rag.ingesta.chunking import ChunkerClinico

logger = logging.getLogger(__name__)

BASE_URL = "https://api.fda.gov"

# Qué campo de la etiqueta va a cada sección del chunk, y con qué título se
# indexa. El orden es el de lectura clínica: para qué sirve, cuánto se da, a
# quién no se le da, qué provoca, con qué choca.
SECCIONES = (
    ("indicaciones", "indications_and_usage", "Indicaciones y uso"),
    ("dosis", "dosage_and_administration", "Dosis y administración"),
    ("contraindicaciones", "contraindications", "Contraindicaciones"),
    ("efectos_adversos", "adverse_reactions", "Reacciones adversas"),
    ("interacciones", "drug_interactions", "Interacciones farmacológicas"),
)


async def _consultar_etiqueta(client: httpx.AsyncClient, search: str) -> Optional[Dict[str, Any]]:
    """
    Lanza una consulta a /drug/label.json y devuelve el primer resultado.

    openFDA responde 404 —no una lista vacía— cuando nada coincide, así que
    "no encontrado" llega como excepción HTTP y hay que distinguirlo de una
    caída real: el 404 devuelve None para que el llamador pruebe otro campo,
    cualquier otro error se propaga.
    """
    response = await client.get(
        f"{BASE_URL}/drug/label.json", params={"search": search, "limit": 1}, timeout=10.0
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    resultados = response.json().get("results") or []
    return resultados[0] if resultados else None


def _primer_valor(openfda: Dict[str, Any], clave: str) -> str:
    valores = openfda.get(clave) or []
    return valores[0] if valores else ""


async def buscar_medicamento(nombre: str) -> Dict[str, Any]:
    """
    Busca la etiqueta de un medicamento en openFDA.

    Prueba primero por nombre comercial y después por genérico. La distinción
    no es cosmética: `edoxaban` no existe como brand_name —su marca es
    Savaysa— y sin el segundo intento el fármaco queda fuera del corpus, que
    es justo lo que pasaba antes.
    """
    logger.info(f"Buscando medicamento en openFDA: {nombre}")
    try:
        async with httpx.AsyncClient() as client:
            resultado = await _consultar_etiqueta(client, f'openfda.brand_name:"{nombre}"')
            if resultado is None:
                logger.info("%s no figura como marca; probando como genérico.", nombre)
                resultado = await _consultar_etiqueta(client, f'openfda.generic_name:"{nombre}"')

        if resultado is None:
            return {"nombre": nombre, "error": "No encontrado"}

        openfda = resultado.get("openfda") or {}
        info = {
            "nombre": nombre,
            "marca": _primer_valor(openfda, "brand_name"),
            "generico": _primer_valor(openfda, "generic_name"),
        }
        for clave, campo, _titulo in SECCIONES:
            info[clave] = "\n".join(resultado.get(campo, []))
        return info
    except Exception as e:
        logger.error(f"Error buscando medicamento {nombre} en openFDA: {e}")
        return {"nombre": nombre, "error": str(e)}


def _etiqueta_farmaco(info: Dict[str, Any]) -> str:
    """
    Encabezado que identifica al fármaco por todos sus nombres conocidos.

    Va dentro del texto del chunk a propósito, no solo en los metadatos: la
    mitad léxica de la búsqueda indexa `texto`, así que si la marca no aparece
    ahí, un estudiante que escribe "Savaysa" no recupera la etiqueta de
    edoxabán por más que el chunk sea exactamente el que necesita.
    """
    nombre = info["nombre"]
    # Clave en minúscula, valor con la grafía original: openFDA devuelve el
    # mismo nombre en mayúsculas en `generic_name` y capitalizado en
    # `brand_name`, y sin normalizar el encabezado queda "Dabigatran
    # (DABIGATRAN ETEXILATE, Dabigatran Etexilate)". El dict preserva el orden
    # de inserción, así que gana la primera grafía vista: genérico antes que marca.
    vistos = {nombre.strip().lower(): nombre}
    for alternativo in (info.get("generico"), info.get("marca")):
        if alternativo and alternativo.strip():
            vistos.setdefault(alternativo.strip().lower(), alternativo.strip())

    alternativos = [v for k, v in vistos.items() if k != nombre.strip().lower()]
    return f"{nombre} ({', '.join(alternativos)})" if alternativos else nombre


def chunkear_medicamento(info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convierte una etiqueta de openFDA en chunks, uno por sección.

    Antes esto era un único chunk con la etiqueta entera concatenada: 17k
    caracteres para dabigatrán. Dos problemas, los dos sobre el validador.
    Uno, el embedding de una etiqueta completa no se parece a "dosis de
    dabigatrán en FA con ClCr 40" —representa el fármaco en general, no esa
    respuesta—. Dos, el validador recibe cuatro fragmentos: si dos son
    etiquetas completas, son 30k caracteres de contexto para verificar una
    dosis, y sobra material para elegir una cita que suene bien pero venga de
    otra sección.

    Cada chunk queda autocontenido —lleva el nombre del fármaco y el título de
    la sección en el texto—, porque se recupera solo, sin sus hermanos.
    """
    if "error" in info:
        return []

    chunker = ChunkerClinico()
    etiqueta = _etiqueta_farmaco(info)
    fuente = f"OpenFDA:{info['nombre']}"
    chunks: List[Dict[str, Any]] = []

    for clave, campo, titulo in SECCIONES:
        fragmentos = chunker.partir_texto(info.get(clave, ""))
        for i, fragmento in enumerate(fragmentos, start=1):
            sufijo = f" [{i}/{len(fragmentos)}]" if len(fragmentos) > 1 else ""
            chunks.append({
                "texto": f"{etiqueta} — {titulo}{sufijo}\n\n{fragmento}",
                "fuente": fuente,
                "seccion": titulo,
                # Solo identificadores. La etiqueta completa NO va acá: los
                # metadatos viajan enteros dentro de cada fila de resultado de
                # `BuscadorHibrido`, y duplicar el texto los volvía el
                # componente más pesado de la respuesta.
                "metadata": {
                    "fuente_api": "openFDA",
                    "campo": campo,
                    "farmaco": info["nombre"],
                    "marca": info.get("marca", ""),
                    "generico": info.get("generico", ""),
                    "titulo": f"{etiqueta} — {titulo}",
                },
            })

    if not chunks:
        logger.warning("La etiqueta de %s no traía ninguna sección con texto.", info["nombre"])

    return chunks


async def obtener_interacciones(nombre_medicamento: str) -> List[Dict[str, Any]]:
    """Obtiene las interacciones documentadas de un medicamento."""
    medicamento = await buscar_medicamento(nombre_medicamento)
    if "error" in medicamento or not medicamento.get("interacciones"):
        return []

    # OpenFDA proporciona texto libre en 'drug_interactions' de las etiquetas.
    # Podríamos estructurar esto más, pero devolver el texto crudo estructurado como dict sirve.
    return [{"medicamento": nombre_medicamento, "descripcion_interaccion": medicamento["interacciones"]}]
