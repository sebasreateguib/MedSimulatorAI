import { useCallback, useRef, useState } from 'react'
import * as api from '../lib/api'
import type { Caso, EstadoSesion, EvaluacionClinica, Mensaje, Rol } from '../types'

let contador = 0
const nuevoId = () => `m${++contador}`

function crearMensaje(rol: Rol, contenido: string, extra?: Partial<Mensaje>): Mensaje {
  return { id: nuevoId(), rol, contenido, timestamp: Date.now(), ...extra }
}

export function useSimulacion() {
  const [caso, setCaso] = useState<Caso | null>(null)
  const [sesionId, setSesionId] = useState<string | null>(null)
  const [estado, setEstado] = useState<EstadoSesion>('inactiva')
  const [mensajes, setMensajes] = useState<Mensaje[]>([])
  const [evaluacion, setEvaluacion] = useState<EvaluacionClinica | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  const abortRef = useRef<AbortController | null>(null)

  const iniciar = useCallback(async (casoElegido: Caso) => {
    setEstado('iniciando')
    setError(null)
    setEvaluacion(null)
    setMensajes([])

    try {
      const { sesion_id } = await api.iniciarSesion(casoElegido.id)
      setSesionId(sesion_id)
      setCaso(casoElegido)
      setEstado('activa')
      setMensajes([
        crearMensaje(
          'sistema',
          `${casoElegido.paciente.nombre}, ${casoElegido.paciente.edad} años. ` +
            `Motivo de consulta: ${casoElegido.motivo_consulta}`,
        ),
      ])
    } catch (err) {
      setEstado('inactiva')
      setError(err instanceof Error ? err.message : 'No se pudo iniciar la sesión.')
    }
  }, [])

  /**
   * Retoma una sesión que quedó abierta: trae el caso y la conversación desde
   * la base y los deja como si nunca se hubiera cerrado la pestaña.
   *
   * Devuelve si pudo, para que quien llama no navegue al simulador cuando la
   * sesión resultó irrecuperable.
   */
  const reanudar = useCallback(async (sesionPedida: string) => {
    setEstado('iniciando')
    setError(null)
    setEvaluacion(null)
    setMensajes([])

    try {
      const sesion = await api.obtenerSesion(sesionPedida)
      setSesionId(String(sesion.sesion_id))
      setCaso(sesion.caso)
      setMensajes(sesion.mensajes.map((m) => crearMensaje(m.rol, m.contenido)))
      // Una sesión ya cerrada se puede mirar, pero no se le puede seguir
      // hablando: el backend rechaza los turnos si no está activa.
      setEstado(sesion.estado === 'activa' ? 'activa' : 'finalizada')
      return true
    } catch (err) {
      setEstado('inactiva')
      setError(err instanceof Error ? err.message : 'No se pudo retomar la sesión.')
      return false
    }
  }, [])

  const enviar = useCallback(
    async (texto: string) => {
      const contenido = texto.trim()
      if (!contenido || !sesionId || enviando) return

      const respuestaId = nuevoId()
      setEnviando(true)
      setError(null)
      setMensajes((prev) => [
        ...prev,
        crearMensaje('estudiante', contenido),
        { id: respuestaId, rol: 'paciente', contenido: '', streaming: true, timestamp: Date.now() },
      ])

      const controller = new AbortController()
      abortRef.current = controller

      const escribirEn = (id: string, fn: (m: Mensaje) => Mensaje) =>
        setMensajes((prev) => prev.map((m) => (m.id === id ? fn(m) : m)))

      // Un turno puede producir varios mensajes de distintos agentes: el
      // resultado de un estudio (sistema) y después la reacción del paciente.
      // `actual` apunta al que está recibiendo tokens en este momento.
      let actual = respuestaId

      try {
        await api.enviarTurno(sesionId, contenido, {
          signal: controller.signal,
          onToken: (token) =>
            escribirEn(actual, (m) => ({ ...m, contenido: m.contenido + token })),
          onRol: (rol) => {
            const anterior = actual
            const idNuevo = nuevoId()
            actual = idNuevo
            setMensajes((prev) => {
              // El mensaje que venía se cierra; si quedó vacío —el marcador
              // llegó antes que cualquier token— se descarta en vez de dejar
              // una burbuja en blanco.
              const cerrados = prev
                .map((m) => (m.id === anterior ? { ...m, streaming: false } : m))
                .filter((m) => m.id !== anterior || m.contenido.trim() !== '')
              return [
                ...cerrados,
                { id: idNuevo, rol, contenido: '', streaming: true, timestamp: Date.now() },
              ]
            })
          },
        })
        escribirEn(actual, (m) => ({ ...m, streaming: false }))
      } catch (err) {
        const mensaje = err instanceof Error ? err.message : 'Error durante el turno.'
        setError(mensaje)
        escribirEn(actual, (m) => ({
          ...m,
          streaming: false,
          error: true,
          contenido: m.contenido || mensaje,
        }))
      } finally {
        abortRef.current = null
        setEnviando(false)
      }
    },
    [sesionId, enviando],
  )

  const detener = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setMensajes((prev) => prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)))
    setEnviando(false)
  }, [])

  const finalizar = useCallback(async () => {
    if (!sesionId) return
    detener()
    setEstado('finalizando')
    setError(null)

    try {
      await api.finalizarSesion(sesionId)
      setEvaluacion(await api.obtenerEvaluacion(sesionId))
      setEstado('finalizada')
    } catch (err) {
      setEstado('activa')
      setError(err instanceof Error ? err.message : 'No se pudo obtener la evaluación.')
    }
  }, [sesionId, detener])

  const reiniciar = useCallback(() => {
    detener()
    setCaso(null)
    setSesionId(null)
    setEstado('inactiva')
    setMensajes([])
    setEvaluacion(null)
    setError(null)
  }, [detener])

  return {
    caso,
    sesionId,
    estado,
    mensajes,
    evaluacion,
    error,
    enviando,
    iniciar,
    reanudar,
    enviar,
    detener,
    finalizar,
    reiniciar,
    descartarError: () => setError(null),
  }
}
