"""
Empaquetado de eventos SSE.

Vive aparte porque los dos streams de la app —el turno de la simulación y el
chat de estudio— tienen que codificar igual: un `f"data: {token}\\n\\n"` crudo
funciona hasta que un token trae un salto de línea, y ahí ese salto termina el
evento antes de tiempo y el cliente pierde el resto. Fue exactamente lo que se
comió el separador "Paciente:" entre el resultado de un estudio y su reacción.
"""


def evento(payload: str) -> str:
    """
    Un evento SSE con el payload dado.

    Los saltos de línea se reparten en varias líneas `data:`, que es lo que
    manda el protocolo; el cliente las vuelve a unir con "\\n".
    """
    cuerpo = payload.replace("\r\n", "\n").replace("\n", "\ndata: ")
    return f"data: {cuerpo}\n\n"
