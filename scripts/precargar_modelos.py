"""
Descarga y precalienta los modelos locales de la ingesta.

Sirve para pagar por adelantado —en el setup o en el build de una imagen— lo que
si no se cobra al primer usuario que sube material: unos 3,5 GB de descarga
(bge-m3, el modelo de layout, el de tablas y el OCR) y el warmup de torch, que
la primera vez lleva un par de minutos.

    python scripts/precargar_modelos.py
"""

import logging
import sys
import time
from pathlib import Path

# Permite ejecutarlo con `python scripts/...` sin instalar el paquete.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from medsimulator.rag.ingesta.materiales import ProcesadorMaterial  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> int:
    inicio = time.time()
    procesador = ProcesadorMaterial()

    print("Descargando y cargando modelos (puede tardar varios minutos)…")
    procesador.precalentar()

    # Verificación real: si el embedding no sale con la dimensión que espera la
    # columna `vector(1024)`, la ingesta fallaría recién al insertar.
    vector = procesador.embedding_service.generar_embedding("prueba de precalentamiento")
    if len(vector) != 1024:
        print(f"✗ El modelo devolvió {len(vector)} dimensiones y la base espera 1024.")
        return 1

    print(f"✓ Modelos listos en {time.time() - inicio:.0f}s (embeddings de {len(vector)} dims).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
