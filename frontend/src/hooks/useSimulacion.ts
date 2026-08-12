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

      try {
        await api.enviarTurno(sesionId, contenido, {
          signal: controller.signal,
          onToken: (token) =>
            escribirEn(respuestaId, (m) => ({ ...m, contenido: m.contenido + token })),
        })
        escribirEn(respuestaId, (m) => ({ ...m, streaming: false }))
      } catch (err) {
        const mensaje = err instanceof Error ? err.message : 'Error durante el turno.'
        setError(mensaje)
        escribirEn(respuestaId, (m) => ({
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
    enviar,
    detener,
    finalizar,
    reiniciar,
    descartarError: () => setError(null),
  }
}
