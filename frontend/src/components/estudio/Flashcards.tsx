import { useCallback, useEffect, useState } from 'react'
import * as api from '../../lib/api'
import { Markdown } from '../Markdown'
import { Repaso } from './Repaso'
import type { Mazo } from '../../types'

const CANTIDADES = [5, 10, 15, 20]

function formatearFecha(iso: string | null): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleDateString('es', { day: '2-digit', month: 'short' })
  } catch {
    return ''
  }
}

interface Props {
  /** Documentos en foco: la generación se limita a ellos si hay alguno. */
  seleccion: number[]
  hayMaterial: boolean
}

export function Flashcards({ seleccion, hayMaterial }: Props) {
  const [mazos, setMazos] = useState<Mazo[]>([])
  const [cargando, setCargando] = useState(true)
  const [tema, setTema] = useState('')
  const [cantidad, setCantidad] = useState(10)
  const [generando, setGenerando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [abierto, setAbierto] = useState<Mazo | null>(null)
  const [repasando, setRepasando] = useState(false)
  // Qué respuestas destapó el usuario en la lista del mazo. Se vacía al abrir
  // otro mazo: si no, el que entra ya aparecería con tarjetas descubiertas.
  const [reveladas, setReveladas] = useState<Set<number>>(new Set())

  const alternarRevelada = (id: number) =>
    setReveladas((prev) => {
      const siguiente = new Set(prev)
      if (!siguiente.delete(id)) siguiente.add(id)
      return siguiente
    })

  const refrescar = useCallback(async () => {
    try {
      setMazos(await api.listarMazos())
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudieron cargar tus mazos.')
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => {
    refrescar()
  }, [refrescar])

  const generar = async () => {
    setGenerando(true)
    setError(null)
    try {
      const mazo = await api.generarMazo({
        documento_ids: seleccion,
        tema: tema.trim() || null,
        cantidad,
      })
      setMazos((prev) => [mazo, ...prev])
      mostrarMazo(mazo)
      setTema('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo generar el mazo.')
    } finally {
      setGenerando(false)
    }
  }

  /** Abre un mazo con todas sus respuestas tapadas. */
  const mostrarMazo = (mazo: Mazo) => {
    setReveladas(new Set())
    setAbierto(mazo)
  }

  const abrir = async (mazo: Mazo) => {
    // El listado no trae las tarjetas: se piden al abrir.
    if (mazo.flashcards.length > 0) {
      mostrarMazo(mazo)
      return
    }
    try {
      mostrarMazo(await api.obtenerMazo(mazo.id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo abrir el mazo.')
    }
  }

  const eliminar = async (id: number) => {
    try {
      await api.eliminarMazo(id)
      setMazos((prev) => prev.filter((m) => m.id !== id))
      setAbierto((prev) => (prev?.id === id ? null : prev))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo eliminar el mazo.')
    }
  }

  if (abierto && repasando) {
    return (
      <Repaso
        mazo={abierto}
        onSalir={() => setRepasando(false)}
        onActualizar={(mazo) => {
          setAbierto(mazo)
          setMazos((prev) => prev.map((m) => (m.id === mazo.id ? { ...m, total: mazo.total } : m)))
        }}
      />
    )
  }

  if (abierto) {
    return (
      <section className="mazo">
        <header className="mazo__cab">
          <div>
            <button type="button" className="mazo__volver mono" onClick={() => setAbierto(null)}>
              ← Mazos
            </button>
            <h2>{abierto.titulo}</h2>
            <p className="rotulo">
              {abierto.flashcards.length} tarjetas
              {abierto.tema ? ` · ${abierto.tema}` : ''}
            </p>
          </div>
          <button type="button" className="btn btn--primario" onClick={() => setRepasando(true)}>
            Repasar
          </button>
        </header>

        <ul className="mazo__lista">
          {abierto.flashcards.map((f) => {
            const revelada = reveladas.has(f.id)
            return (
              <li key={f.id} className={`ficha${revelada ? ' ficha--revelada' : ''}`}>
                {/* La respuesta arranca tapada: verla sin haber intentado
                    recordarla convierte el mazo en un apunte más. */}
                <button
                  type="button"
                  className="ficha__anverso"
                  onClick={() => alternarRevelada(f.id)}
                  aria-expanded={revelada}
                >
                  <span>{f.anverso}</span>
                  <span className="ficha__ojo mono" aria-hidden="true">
                    {revelada ? 'Ocultar' : 'Ver'}
                  </span>
                </button>

                {revelada && (
                  <div className="ficha__reverso">
                    <Markdown texto={f.reverso} />
                  </div>
                )}

                <p className="ficha__pie mono">
                  {f.fuente ?? 'Material'}
                  {f.pagina ? `, pág. ${f.pagina}` : ''}
                  {f.aciertos + f.fallos > 0 ? ` · ${f.aciertos}✓ ${f.fallos}✗` : ''}
                </p>
              </li>
            )
          })}
        </ul>
      </section>
    )
  }

  return (
    <section className="flashcards">
      <div className="flashcards__generador">
        <h2 className="panel__titulo">Generar mazo</h2>
        <p className="flashcards__ayuda">
          {seleccion.length > 0
            ? `Sobre los ${seleccion.length} documento(s) en foco.`
            : 'Sobre todo tu material. Poné documentos en foco para acotarlo.'}
        </p>

        <div className="flashcards__form">
          <input
            type="text"
            value={tema}
            onChange={(e) => setTema(e.target.value)}
            placeholder="Tema (opcional): arritmias, farmacocinética…"
            aria-label="Tema del mazo"
            disabled={generando || !hayMaterial}
          />
          <select
            value={cantidad}
            onChange={(e) => setCantidad(Number(e.target.value))}
            aria-label="Cantidad de tarjetas"
            disabled={generando || !hayMaterial}
          >
            {CANTIDADES.map((n) => (
              <option key={n} value={n}>
                {n} tarjetas
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn btn--primario"
            onClick={generar}
            disabled={generando || !hayMaterial}
          >
            {generando ? 'Generando…' : 'Generar'}
          </button>
        </div>

        {!hayMaterial && (
          <p className="panel__nota">Subí material procesado para poder generar tarjetas.</p>
        )}
      </div>

      {error && (
        <div className="alerta" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => setError(null)} aria-label="Descartar error">
            ×
          </button>
        </div>
      )}

      {cargando && <p className="rotulo">Cargando mazos…</p>}

      {!cargando && mazos.length === 0 && (
        <p className="vacio">Todavía no generaste mazos. El primero sale de lo que ya subiste.</p>
      )}

      <ul className="flashcards__mazos">
        {mazos.map((m) => (
          <li key={m.id} className="mazo-fila">
            <button type="button" className="mazo-fila__cuerpo" onClick={() => abrir(m)}>
              <span className="mazo-fila__titulo">{m.titulo}</span>
              <span className="mazo-fila__meta mono">
                {m.total} tarjetas · {formatearFecha(m.created_at)}
              </span>
            </button>
            <button
              type="button"
              className="documento__accion documento__accion--borrar"
              onClick={() => eliminar(m.id)}
              aria-label={`Eliminar ${m.titulo}`}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
