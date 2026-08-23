"""
Módulo para la partición (chunking) de documentos de guías clínicas.
"""

import logging
from typing import List, Dict, Any, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


class ChunkerClinico:
    """
    Chunker específico para el dominio de guías clínicas.
    Preserva título de sección, número de página, documento fuente y metadatos.

    Las tablas nunca se dividen (quedan como chunk único). El resto del texto
    se acumula en bloques corridos delimitados por tablas y se parte con
    RecursiveCharacterTextSplitter, que respeta párrafos/oraciones en vez de
    cortar a un conteo fijo de caracteres.
    """

    def __init__(self, tamano_chunk: int = 1000, superposicion: int = 200):
        self.tamano_chunk = tamano_chunk
        self.superposicion = superposicion
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=tamano_chunk,
            chunk_overlap=superposicion,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        logger.info(f"Inicializando ChunkerClinico (tamaño: {tamano_chunk}, superposición: {superposicion})")

    def partir_texto(self, texto: str) -> List[str]:
        """
        Parte un texto suelto con la misma política que el resto del corpus.

        Las fuentes que no son PDF —una sección de etiqueta de openFDA, por
        ejemplo— no tienen páginas ni tablas que preservar, pero sí tienen que
        respetar el mismo tamaño de chunk: si una fuente emite bloques de 17k
        caracteres y otra de 1k, el reranker compara peras con manzanas y el
        bloque grande gana por acumulación de términos, no por pertinencia.
        """
        if not texto or not texto.strip():
            return []
        return self._splitter.split_text(texto.strip())

    def chunkear(self, documento: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Divide un documento en chunks preservando el contexto clínico.
        No divide las tablas a la mitad.
        """
        logger.info(f"Generando chunks para el documento: {documento.get('fuente', 'Desconocido')}")
        fuente = documento.get("fuente", "")
        paginas = documento.get("paginas", [])

        chunks: List[Dict[str, Any]] = []
        seccion_actual = "General"
        bloque_actual: List[Dict[str, Any]] = []

        for item in paginas:
            label = item.get("label", "")
            if label in ["title", "section_header"]:
                seccion_actual = item["contenido"].strip()

            if item["tipo"] == "tabla":
                self._volcar_bloque(bloque_actual, fuente, chunks)
                chunks.append(
                    self._crear_chunk(
                        item["contenido"],
                        fuente,
                        [item["numero"]] if item["numero"] else [],
                        seccion_actual,
                        metadata={"tipo": "tabla"},
                    )
                )
            else:
                bloque_actual.append({**item, "seccion": seccion_actual})

        self._volcar_bloque(bloque_actual, fuente, chunks)
        return chunks

    def _volcar_bloque(self, bloque: List[Dict[str, Any]], fuente: str, chunks: List[Dict[str, Any]]) -> None:
        """
        Parte un bloque corrido de texto (sin tablas) en chunks, mapeando cada
        fragmento resultante a las páginas originales que cubre.
        """
        if not bloque:
            return

        texto_bloque = "\n".join(item["contenido"] for item in bloque)
        seccion_bloque = bloque[0]["seccion"]

        # Rango de caracteres [inicio, fin) que ocupa cada página dentro de texto_bloque
        limites_pagina = []
        cursor = 0
        for item in bloque:
            inicio = cursor
            fin = inicio + len(item["contenido"])
            limites_pagina.append((inicio, fin, item["numero"]))
            cursor = fin + 1  # +1 por el "\n" de unión

        cursor_busqueda = 0
        for fragmento in self._splitter.split_text(texto_bloque):
            pos = texto_bloque.find(fragmento, max(0, cursor_busqueda - self.superposicion))
            if pos == -1:
                pos = texto_bloque.find(fragmento)
            fin_fragmento = pos + len(fragmento)

            paginas_fragmento = sorted(
                {p for ini, fin, p in limites_pagina if p and ini < fin_fragmento and fin > pos}
            )
            chunks.append(self._crear_chunk(fragmento, fuente, paginas_fragmento, seccion_bloque))
            cursor_busqueda = fin_fragmento

        bloque.clear()

    def _crear_chunk(
        self,
        texto: str,
        fuente: str,
        paginas: List[int],
        seccion: str,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        return {
            "texto": texto.strip(),
            "fuente": fuente,
            "pagina": paginas[0] if paginas else None,  # Principal página de referencia
            "paginas": paginas,
            "seccion": seccion,
            "metadata": metadata or {},
        }
