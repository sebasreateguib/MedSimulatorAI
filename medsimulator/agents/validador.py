"""
Agente Validador: contrasta lo que afirma el estudiante contra el corpus.

Es el pegamento entre las dos piezas que ya existían por separado: recupera del
corpus los fragmentos pertinentes con `BuscadorHibrido` y se los pasa a un
validador para que emita el veredicto con la cita literal y la página.

Cuál de los dos validadores usa lo decide `config/agents.yaml`: con
`provider: anthropic` y `citations: true` va el nativo, que trae la
fundamentación de fábrica; con cualquier otro proveedor va el casero, que la
consigue verificando la cita contra el texto del chunk.

Degrada en silencio a propósito. Si no hay corpus ingerido, si falta la key o si
el proveedor se cae, `validar()` devuelve un veredicto vacío en vez de
propagar el error: una consulta clínica no se interrumpe porque la verificación
bibliográfica no esté disponible.
"""

import logging
from typing import Any, Dict, List, Optional

from medsimulator.llm.client import get_client_for_agent
from medsimulator.rag.validador_casero import ValidadorCasero
from medsimulator.rag.validador_nativo import ValidadorNativo

logger = logging.getLogger(__name__)

# Cuántos fragmentos se le muestran al validador. Con más, el modelo tiene de
# dónde elegir una cita que suene bien pero venga de otro tema; con menos, una
# afirmación correcta se queda sin respaldo por un fallo de recuperación.
FRAGMENTOS_POR_CONSULTA = 4


class AgenteValidador:
    """Recupera evidencia del corpus y juzga con ella una afirmación clínica."""

    def __init__(self):
        logger.info("Inicializando AgenteValidador")
        self._buscador = None
        self._validador = None
        self.disponible = False

        try:
            client, config = get_client_for_agent("validador")
        except Exception as e:
            logger.warning("Validador no configurado (%s): la validación queda apagada.", e)
            return

        proveedor = config.get("provider", "")
        modelo = config.get("model", "")

        if proveedor == "anthropic" and config.get("citations"):
            self._validador = ValidadorNativo(
                client, modelo, max_tokens=config.get("max_tokens", 1024)
            )
        else:
            self._validador = ValidadorCasero(
                client, modelo, temperature=config.get("temperature", 0.0)
            )

        self.disponible = True
        logger.info(
            "Validador listo: %s sobre %s/%s",
            type(self._validador).__name__, proveedor, modelo,
        )

    # ── Recuperación ────────────────────────────────────────────────

    def _obtener_buscador(self):
        """
        Construye el buscador la primera vez que hace falta.

        No va en `__init__` porque `EmbeddingService` levanta bge-m3 (~2 GB) y
        el orquestador se instancia al abrir cada sesión: pagar esa carga para
        una consulta que quizá nunca valide nada haría que iniciar un caso
        tarde lo que tarda bajar un modelo.
        """
        if self._buscador is None:
            from medsimulator.db import async_session_factory
            from medsimulator.rag.busqueda import BuscadorHibrido
            from medsimulator.rag.embeddings import EmbeddingService

            self._buscador = BuscadorHibrido(async_session_factory, EmbeddingService())
        return self._buscador

    async def _recuperar(self, consulta: str, caso_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            return await self._obtener_buscador().buscar(
                consulta, top_k=FRAGMENTOS_POR_CONSULTA, caso_id=caso_id
            )
        except Exception as e:
            logger.error("No se pudo consultar el corpus: %s", e, exc_info=True)
            return []

    # ── Validación ──────────────────────────────────────────────────

    async def validar(self, afirmacion: str, caso_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Devuelve `{valido, afirmaciones, citas, explicacion}`.

        `valido` es True cuando el corpus respalda la afirmación, False cuando la
        contradice y **None cuando no hay juicio**: sin corpus, sin validador o
        con el proveedor caído. Quien consuma esto tiene que distinguir los tres
        casos —tratar None como False acusaría al estudiante de un error que
        nadie verificó.

        `caso_id` acota la recuperación al material etiquetado para ese caso.
        Omitirlo busca sobre el corpus entero, que es lo que hacía antes de que
        los chunks llevaran etiqueta.
        """
        if not self.disponible or self._validador is None:
            return _sin_juicio("El validador no está configurado.")

        texto = (afirmacion or "").strip()
        if not texto:
            return _sin_juicio("No hay ninguna afirmación que validar.")

        chunks = await self._recuperar(texto, caso_id)
        if not chunks:
            logger.info("Sin fragmentos para '%s': el corpus no cubre el tema o está vacío.", texto[:60])
            return _sin_juicio("El corpus no tiene material sobre este tema.")

        return await self._validador.validar(texto, chunks)

    # ── Presentación ────────────────────────────────────────────────

    @staticmethod
    def formatear(resultado: Dict[str, Any]) -> Optional[str]:
        """
        Arma el bloque en Markdown que ve el estudiante, o None si no hay nada
        que mostrar. Sin veredicto no se dibuja nada: un cartel de "no se pudo
        verificar" en cada receta es ruido, no información.
        """
        if resultado.get("valido") is None:
            return None

        respaldada = resultado["valido"]
        titulo = "**Verificado contra las guías**" if respaldada else "**Contradice las guías**"

        lineas = [titulo]
        if resultado.get("explicacion"):
            lineas.append(resultado["explicacion"])

        for cita in resultado.get("citas", [])[:2]:
            if not cita.get("texto_citado"):
                continue
            referencia = cita.get("documento") or "Fuente desconocida"
            if cita.get("pagina"):
                referencia += f", p. {cita['pagina']}"
            lineas.append(f"> {cita['texto_citado'].strip()}\n>\n> — {referencia}")

        return "\n\n".join(lineas)


def _sin_juicio(motivo: str) -> Dict[str, Any]:
    return {"valido": None, "afirmaciones": [], "citas": [], "explicacion": motivo}
