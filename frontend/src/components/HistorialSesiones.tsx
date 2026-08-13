import { useEffect, useState } from 'react'
import * as api from '../lib/api'
import { evaluacionDemo, preferenciaDemo, sesionesDemo } from '../lib/demo'
import { Scorecard } from './Scorecard'
import type { EvaluacionClinica, SesionHistorial } from '../types'

type Estado = 'cargando' | 'listo' | 'error'

function nivelPuntaje(puntaje: number) {
  if (puntaje >= 80) return 'alto'
  if (puntaje >= 60) return 'medio'
  return 'bajo'
}

function formatearFecha(iso: string) {
  try {
    return new Date(iso).toLocaleString('es', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

interface Props {
  onNuevoCaso: () => void
}

export function HistorialSesiones({ onNuevoCaso }: Props) {
  const [estado, setEstado] = useState<Estado>('cargando')
  const [sesiones, setSesiones] = useState<SesionHistorial[]>([])
  const [error, setError] = useState<string | null>(null)
  const [evaluacionVista, setEvaluacionVista] = useState<EvaluacionClinica | null>(null)
  const [cargandoEvaluacionId, setCargandoEvaluacionId] = useState<string | null>(null)

  // Bloque `demo`: llena el historial con sesiones sintéticas cuando no hay
  // reales (o siempre, con `?demo`). Ver src/lib/demo.ts para borrarlo.
  const preferencia = preferenciaDemo()
  const [demo, setDemo] = useState(preferencia === 'forzado')

  useEffect(() => {
    if (preferencia === 'forzado') {
      setSesiones(sesionesDemo())
      setDemo(true)
      setEstado('listo')
      return
    }
    let vigente = true
    api
      .obtenerHistorial()
      .then((datos) => {
        if (!vigente) return
        const relleno = datos.length === 0 && preferencia === 'auto'
        setSesiones(relleno ? sesionesDemo() : datos)
        setDemo(relleno)
        setEstado('listo')
      })
      .catch((err) => {
        if (!vigente) return
        setError(err instanceof Error ? err.message : 'No se pudo cargar el historial.')
        setEstado('error')
      })
    return () => {
      vigente = false
    }
  }, [preferencia])

  const verEvaluacion = async (sesionId: string) => {
    const sesion = sesiones.find((s) => s.sesion_id === sesionId)
    if (demo && sesion) {
      setEvaluacionVista(evaluacionDemo(sesion))
      return
    }
    setCargandoEvaluacionId(sesionId)
    try {
      setEvaluacionVista(await api.obtenerEvaluacion(sesionId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo cargar la evaluación de esa sesión.')
    } finally {
      setCargandoEvaluacionId(null)
    }
  }

  return (
    <section className="vista-secundaria">
      {demo && (
        <p className="tablero__demo rotulo">Datos de ejemplo — no son tus sesiones</p>
      )}

      <div className="vista-secundaria__intro">
        <h2>Historial de sesiones</h2>
        <p>
          {demo
            ? 'Vista previa del historial con sesiones sintéticas. Tocá un puntaje para ver su evaluación.'
            : 'Los casos que ya simulaste, con el puntaje del tutor cuando la sesión quedó finalizada.'}
        </p>
      </div>

      {estado === 'cargando' && (
        <ul className="historial__lista">
          {[0, 1, 2].map((i) => (
            <li key={i} className="historial__fila historial__fila--skeleton" aria-hidden="true" />
          ))}
        </ul>
      )}

      {estado === 'error' && (
        <div className="alerta" role="alert">
          <span>{error}</span>
        </div>
      )}

      {estado === 'listo' && sesiones.length === 0 && (
        <p className="vacio">Todavía no completaste ninguna sesión. Elegí un caso para empezar.</p>
      )}

      {estado === 'listo' && sesiones.length > 0 && (
        <ul className="historial__lista">
          {sesiones.map((s) => (
            <li key={s.sesion_id} className="historial__fila">
              <div className="historial__info">
                <p className="historial__caso">{s.caso_titulo}</p>
                <p className="historial__meta">
                  {s.paciente_nombre ? `${s.paciente_nombre} · ` : ''}
                  {formatearFecha(s.created_at)}
                </p>
              </div>

              {s.puntaje !== null ? (
                <button
                  type="button"
                  className={`historial__puntaje historial__puntaje--${nivelPuntaje(s.puntaje)}`}
                  onClick={() => verEvaluacion(s.sesion_id)}
                  disabled={cargandoEvaluacionId === s.sesion_id}
                >
                  {cargandoEvaluacionId === s.sesion_id ? '…' : `${s.puntaje}/100`}
                </button>
              ) : (
                <span className="historial__estado mono">
                  {s.estado === 'activa' ? 'En curso' : 'Sin evaluar'}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {evaluacionVista && (
        <Scorecard
          evaluacion={evaluacionVista}
          onCerrar={() => setEvaluacionVista(null)}
          onNuevaSesion={() => {
            setEvaluacionVista(null)
            onNuevoCaso()
          }}
        />
      )}
    </section>
  )
}
