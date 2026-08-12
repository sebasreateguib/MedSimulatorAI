"""
Módulo para la partición (chunking) de documentos de guías clínicas.
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class ChunkerClinico:
    """
    Chunker específico para el dominio de guías clínicas.
    Preserva título de sección, número de página, documento fuente y metadatos.
    """
    
    def __init__(self, tamano_chunk: int = 1000, superposicion: int = 200):
        self.tamano_chunk = tamano_chunk
        self.superposicion = superposicion
        logger.info(f"Inicializando ChunkerClinico (tamaño: {tamano_chunk}, superposición: {superposicion})")

    def chunkear(self, documento: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Divide un documento en chunks preservando el contexto clínico.
        No divide las tablas a la mitad.
        """
        logger.info(f"Generando chunks para el documento: {documento.get('fuente', 'Desconocido')}")
        chunks = []
        fuente = documento.get("fuente", "")
        paginas = documento.get("paginas", [])
        
        seccion_actual = "General"
        buffer_texto = ""
        paginas_buffer = set()
        
        for item in paginas:
            contenido = item["contenido"]
            page_no = item["numero"]
            tipo = item["tipo"]
            label = item.get("label", "")
            
            if label in ["title", "section_header"]:
                seccion_actual = contenido.strip()
            
            if tipo == "tabla":
                # Las tablas se mantienen como chunks únicos
                if buffer_texto:
                    chunks.append(self._crear_chunk(buffer_texto, fuente, list(paginas_buffer), seccion_actual))
                    buffer_texto = ""
                    paginas_buffer.clear()
                    
                chunks.append(self._crear_chunk(contenido, fuente, [page_no] if page_no else [], seccion_actual, metadata={"tipo": "tabla"}))
            else:
                if len(buffer_texto) + len(contenido) > self.tamano_chunk and buffer_texto:
                    chunks.append(self._crear_chunk(buffer_texto, fuente, list(paginas_buffer), seccion_actual))
                    # Retener superposición (aproximación simplificada por palabras)
                    palabras = buffer_texto.split()
                    buffer_texto = " ".join(palabras[-max(1, self.superposicion // 5):]) + "\n" + contenido
                    paginas_buffer = {page_no} if page_no else set()
                else:
                    buffer_texto += "\n" + contenido if buffer_texto else contenido
                    if page_no:
                        paginas_buffer.add(page_no)
        
        if buffer_texto.strip():
            chunks.append(self._crear_chunk(buffer_texto, fuente, list(paginas_buffer), seccion_actual))
            
        return chunks

    def _crear_chunk(self, texto: str, fuente: str, paginas: List[int], seccion: str, metadata: Dict = None) -> Dict[str, Any]:
        return {
            "texto": texto.strip(),
            "fuente": fuente,
            "pagina": paginas[0] if paginas else None, # Principal página de referencia
            "paginas": paginas,
            "seccion": seccion,
            "metadata": metadata or {}
        }
