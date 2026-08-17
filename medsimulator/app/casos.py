"""
Catálogo de casos clínicos leído de `config/casos/*.yaml`.

Un caso se identifica por el campo `id` que declara adentro del archivo, no por
cómo se llame el archivo. Antes la carga armaba la ruta `config/casos/{id}.yaml`
y, como `fa_aguda.yaml` declara `id: fa_aguda_001`, iniciar ese caso daba
"caso no encontrado": el nombre del archivo y la identidad del caso son dos
cosas distintas y nada obligaba a que coincidieran.

Acá viven las dos vistas del mismo dato: la completa —con historia oculta,
laboratorios y diagnóstico— que consume el orquestador, y la pública, que es lo
único que puede ver el estudiante antes de empezar.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

import yaml

logger = logging.getLogger(__name__)

DIRECTORIO_CASOS = Path(__file__).resolve().parent.parent.parent / "config" / "casos"

# Campos que revelan la respuesta del caso. El catálogo público se arma con una
# lista blanca, no descartando estos: si mañana alguien agrega
# `pistas_diagnosticas` al YAML, una lista negra lo dejaría pasar.
DIFICULTAD_POR_DEFECTO = "intermedio"


class CasoNoEncontrado(LookupError):
    """No hay ningún caso con ese id en config/casos/."""


def cargar_catalogo() -> Dict[str, Dict[str, Any]]:
    """
    Devuelve todos los casos indexados por su id declarado.

    Se relee el directorio en cada llamada a propósito: son unos pocos archivos
    chicos, y cachearlos obligaría a reiniciar el backend para ver un caso nuevo.
    """
    catalogo: Dict[str, Dict[str, Any]] = {}

    if not DIRECTORIO_CASOS.is_dir():
        logger.error(f"No existe el directorio de casos: {DIRECTORIO_CASOS}")
        return catalogo

    for ruta in sorted(DIRECTORIO_CASOS.glob("*.y*ml")):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                caso = yaml.safe_load(f)
        except yaml.YAMLError as e:
            # Un YAML roto no puede tumbar el catálogo entero: se saltea y se
            # avisa, así los demás casos siguen disponibles.
            logger.error(f"Caso ilegible en {ruta.name}: {e}")
            continue

        if not isinstance(caso, dict):
            logger.error(f"El caso {ruta.name} no es un mapeo YAML; se ignora.")
            continue

        # Sin `id` declarado, el nombre del archivo hace de identidad.
        caso_id = str(caso.get("id") or ruta.stem).strip()
        if caso_id in catalogo:
            logger.warning(
                f"El id '{caso_id}' está repetido: {ruta.name} pisa al anterior."
            )

        caso["id"] = caso_id
        caso["_archivo"] = ruta.name
        catalogo[caso_id] = caso

    return catalogo


def cargar_caso(caso_id: str) -> Dict[str, Any]:
    """Caso completo por id. Lanza `CasoNoEncontrado` si no está."""
    catalogo = cargar_catalogo()
    caso = catalogo.get(caso_id)

    if caso is None:
        disponibles = ", ".join(sorted(catalogo)) or "ninguno"
        logger.error(f"Caso '{caso_id}' no encontrado. Disponibles: {disponibles}")
        raise CasoNoEncontrado(
            f"Caso clínico '{caso_id}' no encontrado. Disponibles: {disponibles}."
        )

    return caso


def motivo_de_consulta(caso: Dict[str, Any]) -> str:
    """
    El motivo declarado o, si falta, el que se desprende de los síntomas: es lo
    que el estudiante lee para elegir el caso y no puede quedar vacío.
    """
    motivo = (caso.get("motivo_consulta") or "").strip()
    if motivo:
        return motivo

    sintomas = caso.get("paciente", {}).get("sintomas") or caso.get("sintomas") or []
    if sintomas:
        return ", ".join(str(s) for s in sintomas[:2]) + "."
    return "Consulta clínica."


def caso_publico(caso: Dict[str, Any]) -> Dict[str, Any]:
    """
    Vista que puede ver el estudiante antes de empezar: quién consulta y por
    qué. Todo lo demás —historia oculta, laboratorios, ECG, diagnóstico, plan—
    se resuelve durante la simulación y no viaja al navegador.
    """
    paciente = caso.get("paciente", {})
    return {
        "id": caso["id"],
        "titulo": caso.get("titulo", "Caso sin título"),
        "motivo_consulta": motivo_de_consulta(caso),
        "paciente": {
            "nombre": paciente.get("nombre", "Paciente"),
            "edad": paciente.get("edad", 0),
            "genero": paciente.get("genero", "No especificado"),
        },
        "dificultad": caso.get("dificultad", DIFICULTAD_POR_DEFECTO),
    }


def catalogo_publico() -> List[Dict[str, Any]]:
    """Lista de casos disponibles, ordenada por título."""
    casos = [caso_publico(c) for c in cargar_catalogo().values()]
    return sorted(casos, key=lambda c: c["titulo"])
