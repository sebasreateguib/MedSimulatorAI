"""
Router para los endpoints relacionados con la evaluación de la simulación.
"""
import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from medsimulator.db import get_db
from medsimulator.db.models import Sesion, Evaluacion
from medsimulator.llm.schemas import EvaluacionClinica

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/{sesion_id}")
async def obtener_evaluacion(sesion_id: int, db: AsyncSession = Depends(get_db)):
    """
    Obtiene el scorecard o evaluación detallada de una sesión finalizada.
    """
    # Verificar si la sesión existe
    sesion_result = await db.execute(select(Sesion).where(Sesion.id == sesion_id))
    sesion = sesion_result.scalar_one_or_none()
    
    if not sesion:
        logger.warning(f"Intento de obtener evaluación para sesión inexistente: {sesion_id}")
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")

    # Obtener evaluación
    eval_result = await db.execute(select(Evaluacion).where(Evaluacion.sesion_id == sesion_id))
    evaluacion = eval_result.scalar_one_or_none()

    if not evaluacion:
        if sesion.estado != "finalizada":
            raise HTTPException(status_code=400, detail="La sesión aún no ha sido finalizada y no tiene evaluación.")
        else:
            # Caso anómalo: sesión finalizada pero sin evaluación generada
            raise HTTPException(status_code=404, detail="Evaluación no encontrada para esta sesión.")
            
    # Si tenemos el objeto de evaluación clínica en formato JSON (como debería estar en nuestro modelo)
    eval_data = evaluacion.evaluacion_clinica
    if eval_data:
        try:
            return EvaluacionClinica(**eval_data)
        except Exception as e:
            logger.error(f"Error parseando la evaluación clínica JSON en la base de datos para la sesión {sesion_id}: {e}")
            # Retorno fallback si el JSON estaba malformado o no coincide
            return {
                "sesion_id": sesion_id,
                "score_general": evaluacion.puntaje,
                "feedback": evaluacion.feedback,
                "datos_crudos": eval_data
            }
            
    return {
        "sesion_id": sesion_id,
        "score_general": evaluacion.puntaje,
        "feedback": evaluacion.feedback
    }
