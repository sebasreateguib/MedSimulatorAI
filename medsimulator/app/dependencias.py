"""
Dependencias de FastAPI compartidas: resolución del usuario autenticado a
partir del JWT y verificación de propiedad sobre los recursos.
"""
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medsimulator.app.security import leer_token_acceso
from medsimulator.db import get_db
from medsimulator.db.models import Sesion, Usuario

logger = logging.getLogger(__name__)

# auto_error=False para poder responder 401 (y no el 403 que trae por defecto)
# cuando falta el header Authorization.
esquema_bearer = HTTPBearer(auto_error=False)

CREDENCIALES_INVALIDAS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No autenticado o token inválido.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer),
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    """
    Resuelve el usuario dueño del token. Lanza 401 si el token falta, es
    inválido, expiró o apunta a un usuario que ya no existe.
    """
    if credenciales is None:
        raise CREDENCIALES_INVALIDAS

    usuario_id = leer_token_acceso(credenciales.credentials)
    if usuario_id is None:
        raise CREDENCIALES_INVALIDAS

    resultado = await db.execute(select(Usuario).where(Usuario.id == usuario_id))
    usuario = resultado.scalar_one_or_none()
    if usuario is None:
        # Token con firma válida pero de un usuario borrado.
        raise CREDENCIALES_INVALIDAS

    return usuario


async def sesion_del_usuario(
    sesion_id: int,
    usuario: Usuario,
    db: AsyncSession,
) -> Sesion:
    """
    Devuelve la sesión pedida solo si pertenece al usuario autenticado.

    Responde 404 (y no 403) cuando la sesión existe pero es de otro usuario:
    confirmar su existencia permitiría enumerar sesiones ajenas por id.
    """
    resultado = await db.execute(select(Sesion).where(Sesion.id == sesion_id))
    sesion = resultado.scalar_one_or_none()

    if sesion is None or sesion.usuario_id != usuario.id:
        if sesion is not None:
            logger.warning(
                f"Usuario {usuario.id} intentó acceder a la sesión {sesion_id}, "
                f"que pertenece al usuario {sesion.usuario_id}."
            )
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")

    return sesion
