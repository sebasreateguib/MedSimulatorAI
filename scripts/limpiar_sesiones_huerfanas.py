"""
Borra sesiones que quedaron "activas" y ya no se pueden retomar.

Contexto: hasta ahora la conversación de una sesión solo vivía en memoria del
proceso y `finalizar` fallaba con 422 porque el frontend mandaba `sesion_id` en
la URL y el endpoint lo espera en el cuerpo. El resultado eran sesiones
inmortales: figuraban "en curso" en el historial y no había forma de cerrarlas
ni de seguirlas.

Con la persistencia en `transcripciones` eso no vuelve a pasar, pero las
sesiones viejas no tienen ni un mensaje guardado: no hay nada que retomar.
Este script las saca del historial.

Solo toca sesiones activas SIN transcripciones. Una sesión activa que sí tenga
conversación guardada es retomable y no se toca nunca.

Uso:
    python -m scripts.limpiar_sesiones_huerfanas            # lista, no borra
    python -m scripts.limpiar_sesiones_huerfanas --borrar   # borra de verdad
"""
import argparse
import asyncio
import sys

from sqlalchemy import delete, func, select

from medsimulator.db import async_session_factory
from medsimulator.db.models import Evaluacion, Sesion, Transcripcion


async def huerfanas(db) -> list[Sesion]:
    """Sesiones activas sin un solo mensaje persistido."""
    n_mensajes = (
        select(func.count(Transcripcion.id))
        .where(Transcripcion.sesion_id == Sesion.id)
        .scalar_subquery()
    )
    resultado = await db.execute(
        select(Sesion)
        .where(Sesion.estado == "activa", n_mensajes == 0)
        .order_by(Sesion.created_at)
    )
    return list(resultado.scalars().all())


async def main(borrar: bool) -> int:
    async with async_session_factory() as db:
        sesiones = await huerfanas(db)

        if not sesiones:
            print("No hay sesiones huérfanas. Nada que hacer.")
            return 0

        print(f"{len(sesiones)} sesión(es) activa(s) sin conversación guardada:\n")
        for s in sesiones:
            caso = (s.caso_data or {}).get("titulo", "Caso sin título")
            print(f"  #{s.id:<5} {s.created_at:%Y-%m-%d %H:%M}  usuario {s.usuario_id}  {caso}")

        if not borrar:
            print("\nDry run: no se borró nada.")
            print("Volvé a correrlo con --borrar para eliminarlas.")
            return 0

        ids = [s.id for s in sesiones]
        # Por si alguna tuviera evaluación colgando: sin esto la FK aborta.
        await db.execute(delete(Evaluacion).where(Evaluacion.sesion_id.in_(ids)))
        await db.execute(delete(Sesion).where(Sesion.id.in_(ids)))
        await db.commit()
        print(f"\nBorradas {len(ids)} sesión(es): {ids}")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--borrar",
        action="store_true",
        help="Ejecuta el borrado. Sin este flag solo lista.",
    )
    sys.exit(asyncio.run(main(parser.parse_args().borrar)))
