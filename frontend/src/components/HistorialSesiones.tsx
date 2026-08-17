import { useEffect, useState } from 'react'
import * as api from '../lib/api'
import { evaluacionDemo, preferenciaDemo, sesionesDemo } from '../lib/demo'
import { Scorecard } from './Scorecard'
import type { EvaluacionClinica, SesionHistorial } from '../types'

type Estado = 'cargando' | 'listo' | 'error'

/** Sesiones por página. El backend recorta con `limite`/`desplazamiento`. */
const POR_PAGINA = 5

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
  /** Retoma una sesión abierta. Devuelve si pudo, para no navegar en falso. */
  onReanudar: (sesionId: string) => Promise<boolean>
}

export function HistorialSesiones({ onNuevoCaso, onReanudar }: Props) {
  const [estado, setEstado] = useState<Estado>('cargando')
  const [sesiones, setSesiones] = useState<SesionHistorial[]>([])
  const [error, setError] = useState<string | null>(null)
  const [evaluacionVista, setEvaluacionVista] = useState<EvaluacionClinica | null>(null)
  const [cargandoEvaluacionId, setCargandoEvaluacionId] = useState<string | null>(null)
  const [reanudandoId, setReanudandoId] = useState<string | null>(null)
  const [pagina, setPagina] = useState(0)
  const [total, setTotal] = useState(0)
  /** Distinto de `estado`: al cambiar de página la lista ya existe y solo se
      atenúa, en vez de volver al esqueleto y hacer saltar el layout. */
  const [cambiandoPagina, setCambiandoPagina] = useState(false)

  // Bloque `demo`: llena el historial con sesiones sintéticas cuando no hay
  // reales (o siempre, con `?demo`). Ver src/lib/demo.ts para borrarlo.
  const preferencia = preferenciaDemo()
  const [demo, setDemo] = useState(preferencia === 'forzado')

  useEffect(() => {
    // Las sesiones sintéticas son deterministas (PRNG con semilla fija), así
    // que recortarlas por página da siempre el mismo reparto.
    const paginaDemo = () => {
      const todas = sesionesDemo()
      setSesiones(todas.slice(pagina * POR_PAGINA, (pagina + 1) * POR_PAGINA))
      setTotal(todas.length)
    }

    if (preferencia === 'forzado') {
      paginaDemo()
      setDemo(true)
      setEstado('listo')
      return
    }

    let vigente = true
    setCambiandoPagina(true)
    api
      .obtenerPaginaHistorial(POR_PAGINA, pagina * POR_PAGINA)
      .then((datos) => {
        if (!vigente) return
        const relleno = datos.total === 0 && preferencia === 'auto'
        if (relleno) {
          paginaDemo()
        } else {
          setSesiones(datos.sesiones)
          setTotal(datos.total)
        }
        setDemo(relleno)
        setEstado('listo')
      })
      .catch((err) => {
        if (!vigente) return
        setError(err instanceof Error ? err.message : 'No se pudo cargar el historial.')
        setEstado('error')
      })
      .finally(() => {
        if (vigente) setCambiandoPagina(false)
      })
    return () => {
      vigente = false
    }
  }, [preferencia, pagina])

  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA))
  const desde = total === 0 ? 0 : pagina * POR_PAGINA + 1
  const hasta = Math.min(total, pagina * POR_PAGINA + sesiones.length)

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

  const retomar = async (sesionId: string) => {
    if (reanudandoId) return
    setReanudandoId(sesionId)
    setError(null)
    // Si falla, `onReanudar` deja el mensaje en el error global de la app y no
    // se navega: la fila vuelve a quedar disponible.
    const pudo = await onReanudar(sesionId)
    if (!pudo) setReanudandoId(null)
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
        <ul
          className={
            cambiandoPagina ? 'historial__lista historial__lista--cambiando' : 'historial__lista'
          }
        >
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
              ) : s.estado === 'activa' && !demo ? (
                // Una sesión abierta se retoma donde quedó. En demo no: las
                // sesiones sintéticas no existen en la base.
                <button
                  type="button"
                  className="btn btn--fantasma historial__retomar"
                  onClick={() => retomar(s.sesion_id)}
                  disabled={reanudandoId !== null}
                >
                  {reanudandoId === s.sesion_id ? 'Abriendo…' : 'Retomar'}
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

      {/* La paginación aparece recién cuando hay más de una página: con cinco
          sesiones o menos, unos controles que no llevan a ningún lado. */}
      {estado === 'listo' && paginas > 1 && (
        <nav className="paginador" aria-label="Páginas del historial">
          <button
            type="button"
            className="btn btn--fantasma"
            onClick={() => setPagina((p) => Math.max(0, p - 1))}
            disabled={pagina === 0 || cambiandoPagina}
          >
            Anteriores
          </button>

          <p className="paginador__cuenta mono" aria-live="polite">
            {desde}–{hasta} de {total}
            <span className="paginador__pagina">
              página {pagina + 1} de {paginas}
            </span>
          </p>

          <button
            type="button"
            className="btn btn--fantasma"
            onClick={() => setPagina((p) => Math.min(paginas - 1, p + 1))}
            disabled={pagina >= paginas - 1 || cambiandoPagina}
          >
            Siguientes
          </button>
        </nav>
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
