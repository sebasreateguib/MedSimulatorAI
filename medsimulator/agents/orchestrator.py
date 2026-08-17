"""
Loop principal de orquestación para MedSimulator AI.
"""
import asyncio
import logging
from typing import AsyncGenerator, Any, Dict, List

from medsimulator.app.casos import cargar_caso
from medsimulator.agents.router import AgenteRouter
from medsimulator.agents.tools import identificar_laboratorios, nombre_estudio
from medsimulator.agents.paciente import AgentePaciente
from medsimulator.agents.especialista import AgenteEspecialista
from medsimulator.agents.tutor import AgenteTutor
from medsimulator.agents.validador import AgenteValidador
from medsimulator.agents.tools import procesar_herramienta
from medsimulator.llm.schemas import EvaluacionClinica

logger = logging.getLogger(__name__)

# Intención del router → herramienta de tools.py. El mapeo explícito existe
# porque los nombres no coinciden: el router dice "receta" y "diagnostico", y
# las herramientas se llaman "recetar" y "diagnosticar". Cuando esto se armaba
# concatenando strings, esas dos intenciones caían en "herramienta no soportada"
# y ni recetar ni diagnosticar hacían nada.
HERRAMIENTA_POR_INTENCION = {
    "laboratorio": "pedir_laboratorio",
    "imagen": "pedir_imagen",
    "receta": "recetar",
    "diagnostico": "diagnosticar",
}

# Marcador de control del stream: le indica al frontend de qué agente es lo que
# viene, para que abra un mensaje nuevo en vez de concatenarlo al anterior.
MARCA_ROL = "[ROL:{rol}]"

# Qué se le dice al paciente para que reaccione a cada acción del estudiante.
# Un "acaba de pedir_imagen" le llegaba con el nombre de la función adentro.
PEDIDO_DE_REACCION = {
    "pedir_laboratorio": "El doctor acaba de indicarte unos análisis de sangre. ¿Cómo reaccionás?",
    "pedir_imagen": "El doctor acaba de indicarte un estudio por imágenes. ¿Cómo reaccionás?",
    "recetar": "El doctor acaba de indicarte un tratamiento. ¿Cómo reaccionás?",
    "diagnosticar": "El doctor acaba de decirte qué cree que tenés. ¿Cómo reaccionás?",
}

# Qué acciones se contrastan contra el corpus. Son las dos en las que el
# estudiante afirma algo verificable —un fármaco con su dosis, un diagnóstico—;
# pedir un laboratorio no afirma nada que una guía pueda respaldar o contradecir.
HERRAMIENTAS_VALIDABLES = ("recetar", "diagnosticar")

# La validación corre dentro del turno, así que su latencia la espera el
# estudiante. Pasado este tope se sigue sin ella: mejor un turno sin cita que un
# turno colgado esperando al buscador.
TIEMPO_MAXIMO_VALIDACION = 25.0


def formatear_resultado(herramienta: str, argumentos: dict, resultado: dict) -> str:
    """
    Arma el mensaje que ve el estudiante cuando vuelve un estudio o se registra
    una acción.

    Sale en Markdown, que la interfaz ahora renderiza: antes se emitía
    `[PEDIR_IMAGEN]: ... {'clave': 'valor'}`, con el nombre de la función y el
    diccionario de Python crudos en medio de la conversación.
    """
    if herramienta == "pedir_imagen":
        titulo = argumentos.get("tipo_estudio", "Estudio")
        cuerpo = resultado.get("resultados") or resultado.get("mensaje", "")
        return f"**{titulo}**\n\n{cuerpo}"

    if herramienta == "pedir_laboratorio":
        resultados = resultado.get("resultados") or {}
        if not resultados:
            return "**Laboratorio**\n\nNo hay resultados para las pruebas solicitadas."
        filas = "\n".join(
            f"- **{clave.replace('_', ' ').capitalize()}**: {valor}"
            for clave, valor in resultados.items()
        )
        faltantes = resultado.get("sin_resultado") or []
        nota = f"\n\nSin resultado en este caso: {', '.join(faltantes)}." if faltantes else ""
        return f"**Laboratorio**\n\n{filas}{nota}"

    if herramienta == "recetar":
        indicado = "\n".join(f"- {m}" for m in argumentos.get("medicamentos", []))
        return f"**Indicación registrada**\n\n{indicado}"

    if herramienta == "diagnosticar":
        principal = argumentos.get("diagnostico_principal", "")
        return f"**Diagnóstico registrado**\n\n{principal}"

    return resultado.get("mensaje", "")


class Orchestrator:
    """
    Orquestador principal que maneja el ciclo de vida de la sesión
    y enruta los mensajes entre el usuario y los agentes.
    """
    def __init__(self):
        logger.info("Inicializando Orchestrator")
        self.router = AgenteRouter()
        self.paciente = AgentePaciente()
        self.especialista = AgenteEspecialista()
        self.tutor = AgenteTutor()
        self.validador = AgenteValidador()
        self.historial: List[Dict[str, Any]] = []
        self.caso: Dict[str, Any] = {}
        self.sesion_id: str = ""

    async def iniciar_sesion(self, caso_id: str) -> Dict[str, Any]:
        """
        Inicializa una nueva sesión clínica.
        """
        logger.info(f"Iniciando sesión para caso: {caso_id}")
        self.historial = []
        self.sesion_id = f"sesion_{caso_id}"
        
        # El caso se busca por el `id` que declara adentro del YAML, no por el
        # nombre del archivo: ver medsimulator/app/casos.py.
        self.caso = cargar_caso(caso_id)


        # Generar un mensaje de bienvenida de parte del sistema
        paciente_nombre = self.caso.get("paciente", {}).get("nombre", "el paciente")
        mensaje_inicial = f"El paciente {paciente_nombre} ha ingresado a tu consultorio."
        self.historial.append({"role": "system", "content": mensaje_inicial})
        
        return {
            "status": "started", 
            "caso": caso_id,
            "mensaje_inicial": mensaje_inicial,
            "paciente_info": self.caso.get("paciente", {})
        }

    def restaurar(self, caso: Dict[str, Any], historial: List[Dict[str, Any]]) -> None:
        """
        Rehidrata el orquestador con una sesión que ya venía empezada.

        Es la contracara de `iniciar_sesion`: no inventa mensaje de bienvenida
        ni vuelve a leer el YAML, porque el caso llega del snapshot que se
        guardó al iniciar la sesión (`Sesion.caso_data`). Así una sesión
        retomada arranca con la consulta entera en contexto.

        Antes esto no existía y el router recreaba el orquestador llamando a
        `iniciar_sesion()`: la sesión conservaba su id y seguía respondiendo,
        pero con el historial vacío. El paciente había olvidado toda la
        consulta y nada lo indicaba.

        Limitación conocida: los eventos estructurados que el tutor registra
        con `registrar_evento` (qué herramienta se usó, con qué argumentos) no
        se persisten, así que una sesión retomada los pierde. El tutor todavía
        ve el resultado de cada estudio, porque quedó como mensaje de sistema
        en el historial, pero evalúa con menos detalle que una sesión corrida
        de una sola vez.
        """
        self.caso = caso or {}
        self.historial = list(historial)
        self.sesion_id = f"sesion_{self.caso.get('id', 'desconocido')}"
        logger.info(
            f"Orquestador restaurado para caso '{self.caso.get('id', 'desconocido')}' "
            f"con {len(self.historial)} mensajes de contexto"
        )

    async def procesar_turno(self, entrada_estudiante: str) -> AsyncGenerator[str, None]:
        """
        Procesa un turno enviando la entrada del estudiante al loop de agentes.
        Soporta streaming SSE.
        """
        logger.debug(f"Procesando turno: {entrada_estudiante[:50]}...")
        self.historial.append({"role": "user", "content": entrada_estudiante})
        
        # 1. Enviar a Router para clasificar intención
        intencion = await self.router.clasificar(entrada_estudiante)
        logger.info(f"Intención clasificada: {intencion}")
        
        # 2. Despachar según intención
        respuesta_final = ""
        
        if intencion in ["anamnesis", "otro"]:
            # Hablar con el paciente con streaming
            async for chunk in self.paciente.responder_stream(entrada_estudiante, self.historial, self.caso):
                respuesta_final += chunk
                yield chunk
                
            self.historial.append({"role": "assistant", "content": respuesta_final})
            
        elif intencion in HERRAMIENTA_POR_INTENCION:
            # El router da la intención; los argumentos salen del texto del
            # estudiante. Antes estaban fijos ("tipo_estudio": "ECG"), así que
            # pedir una radiografía devolvía el trazado del electro.
            herramienta = HERRAMIENTA_POR_INTENCION[intencion]
            argumentos = self._argumentos_de(intencion, entrada_estudiante)

            resultado = procesar_herramienta(herramienta, argumentos, self.caso)

            self.tutor.registrar_evento({
                "herramienta": herramienta,
                "argumentos": argumentos,
                "resultado": resultado,
            })

            # El resultado es del sistema, no del paciente: va en su propio
            # mensaje. El marcador de rol le dice al frontend que abra una
            # burbuja nueva en vez de pegarlo a lo que venía.
            mensaje_sistema = formatear_resultado(herramienta, argumentos, resultado)
            yield MARCA_ROL.format(rol="sistema")
            yield mensaje_sistema
            self.historial.append({"role": "system", "content": mensaje_sistema})

            # Lo que el estudiante indicó o diagnosticó se contrasta con las
            # guías antes de que el paciente reaccione: la cita pertenece al
            # acto clínico, no al comentario que viene después.
            if herramienta in HERRAMIENTAS_VALIDABLES:
                veredicto = await self._validar(entrada_estudiante)
                if veredicto:
                    yield MARCA_ROL.format(rol="sistema")
                    yield veredicto
                    self.historial.append({"role": "system", "content": veredicto})

            # Y recién ahí reacciona el paciente, en otra burbuja.
            yield MARCA_ROL.format(rol="paciente")
            reaccion = ""
            async for chunk in self.paciente.responder_stream(
                PEDIDO_DE_REACCION.get(herramienta, "El doctor acaba de indicar algo. ¿Cómo reaccionas?"),
                self.historial,
                self.caso,
            ):
                reaccion += chunk
                yield chunk

            self.historial.append({"role": "assistant", "content": reaccion})
            
        elif intencion == "interconsulta":
            # Llamar al especialista
            # Extraer especialidad rudimentariamente
            especialidad = "cardiologia"
            for esp in AgenteEspecialista.ESPECIALIDADES.keys():
                if esp in entrada_estudiante.lower():
                    especialidad = esp
                    break
                    
            respuesta_esp = await self.especialista.consultar(especialidad, entrada_estudiante, self.caso)

            # La respuesta del especialista es de otro agente: burbuja propia,
            # con su rótulo, en vez de mezclarse con la voz del paciente.
            yield MARCA_ROL.format(rol="especialista")

            # Stream falso ya que el especialista no usa streaming en su config
            for palabra in respuesta_esp.split():
                chunk = palabra + " "
                respuesta_final += chunk
                yield chunk

            self.historial.append({"role": "assistant", "content": f"[Especialista]: {respuesta_final}"})

    async def _validar(self, afirmacion: str) -> str:
        """
        Contrasta la acción del estudiante contra el corpus y devuelve el bloque
        a mostrar, o cadena vacía si no hay nada que decir.

        Nada de lo que pase acá adentro puede tumbar el turno: el circuito
        clínico funcionaba antes de que existiera el validador y tiene que
        seguir funcionando cuando el corpus esté vacío o el proveedor se caiga.
        """
        if not self.validador.disponible:
            return ""

        try:
            resultado = await asyncio.wait_for(
                self.validador.validar(afirmacion), timeout=TIEMPO_MAXIMO_VALIDACION
            )
        except asyncio.TimeoutError:
            logger.warning("La validación superó los %ss; se sigue sin ella.", TIEMPO_MAXIMO_VALIDACION)
            return ""
        except Exception as e:
            logger.error("Error validando contra el corpus: %s", e, exc_info=True)
            return ""

        # El tutor lo registra aunque no se muestre: una afirmación que el corpus
        # contradice pesa en la evaluación final incluso si la cita no se dibujó.
        self.tutor.registrar_evento({"herramienta": "validar", "argumentos": {"afirmacion": afirmacion}, "resultado": resultado})

        return AgenteValidador.formatear(resultado) or ""

    def _argumentos_de(self, intencion: str, entrada: str) -> Dict[str, Any]:
        """
        Traduce lo que escribió el estudiante a los argumentos de la herramienta.

        Es un extractor por palabras clave, no un modelo con function calling:
        alcanza para saber qué estudio se pidió y evita una llamada más al LLM
        en cada acción. Lo que no reconoce se pasa tal cual, así el tutor
        siempre evalúa el texto real.
        """
        if intencion == "laboratorio":
            disponibles = self.caso.get("resultados_laboratorio", self.caso.get("laboratorios", {})) or {}
            return {
                "pruebas": identificar_laboratorios(entrada, disponibles),
                "justificacion": entrada,
            }

        if intencion == "imagen":
            return {"tipo_estudio": nombre_estudio(entrada), "justificacion": entrada}

        if intencion == "receta":
            return {"medicamentos": [entrada.strip()]}

        return {"diagnostico_principal": entrada.strip()}

    async def finalizar_sesion(self) -> EvaluacionClinica:
        """
        Finaliza la sesión actual y solicita la evaluación final al Tutor.
        """
        logger.info("Finalizando sesión")
        evaluacion = await self.tutor.evaluar_final(self.historial, self.caso)
        return evaluacion
