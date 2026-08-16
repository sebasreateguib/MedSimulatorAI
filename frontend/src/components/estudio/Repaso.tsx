import { useState } from 'react'
import * as api from '../../lib/api'
import { Markdown } from '../Markdown'
import type { Flashcard, Mazo } from '../../types'

/**
 * Peor sabidas primero: lo que más se falló abre la sesión, y a igualdad de
 * saldo va antes lo que nunca se vio. Sin esto el repaso empieza siempre por
 * las mismas tarjetas fáciles del principio del mazo.
 */
function ordenarPorDificultad(flashcards: Flashcard[]): Flashcard[] {
  return [...flashcards].sort((a, b) => {
    const saldoA = a.aciertos - a.fallos
    const saldoB = b.aciertos - b.fallos
    if (saldoA !== saldoB) return saldoA - saldoB
    return a.aciertos + a.fallos - (b.aciertos + b.fallos)
  })
}

interface Props {
  mazo: Mazo
  onSalir: () => void
  onActualizar: (mazo: Mazo) => void
}

export function Repaso({ mazo, onSalir, onActualizar }: Props) {
  // Se congela al montar. Con `useMemo` no alcanzaría: cada respuesta actualiza
  // los contadores del mazo, la dependencia cambia y el orden se recalcularía
  // debajo de la tarjeta que se está mirando.
  const [orden] = useState(() => ordenarPorDificultad(mazo.flashcards))

  const [indice, setIndice] = useState(0)
  const [revelada, setRevelada] = useState(false)
  const [aciertos, setAciertos] = useState(0)

  const ficha = orden[indice]
  const terminado = indice >= orden.length

  const responder = async (resultado: 'bien' | 'mal') => {
    if (!ficha) return
    if (resultado === 'bien') setAciertos((n) => n + 1)

    setRevelada(false)
    setIndice((n) => n + 1)

    try {
      const actualizada = await api.registrarRepaso(ficha.id, resultado)
      onActualizar({
        ...mazo,
        flashcards: mazo.flashcards.map((f) => (f.id === actualizada.id ? actualizada : f)),
      })
    } catch {
      // El repaso no se corta porque no se haya podido anotar el resultado:
      // la tarjeta ya se respondió y el conteo local sigue siendo válido.
    }
  }

  if (terminado) {
    return (
      <section className="repaso">
        <div className="repaso__final">
          <p className="rotulo">Repaso terminado</p>
          <p className="repaso__marcador">
            {aciertos}
            <span>/{orden.length}</span>
          </p>
          <p>
            {aciertos === orden.length
              ? 'Mazo entero. Generá uno nuevo sobre otro tema del material.'
              : 'Las que fallaste van a aparecer primero la próxima vez.'}
          </p>
          <div className="repaso__acciones">
            <button
              type="button"
              className="btn btn--secundario"
              onClick={() => {
                setIndice(0)
                setAciertos(0)
                setRevelada(false)
              }}
            >
              Repetir
            </button>
            <button type="button" className="btn btn--primario" onClick={onSalir}>
              Volver al mazo
            </button>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="repaso">
      <header className="repaso__cab">
        <button type="button" className="mazo__volver mono" onClick={onSalir}>
          ← Salir
        </button>
        <p className="rotulo">
          {indice + 1} / {orden.length} · {mazo.titulo}
        </p>
      </header>

      <div className="repaso__barra">
        <span style={{ width: `${(indice / orden.length) * 100}%` }} />
      </div>

      <div className={`tarjeta${revelada ? ' tarjeta--revelada' : ''}`}>
        <p className="tarjeta__anverso">{ficha.anverso}</p>
        {revelada && (
          <>
            <hr className="tarjeta__linea" />
            <div className="tarjeta__reverso">
              <Markdown texto={ficha.reverso} />
            </div>
            <p className="tarjeta__fuente mono">
              {ficha.fuente ?? 'Material'}
              {ficha.pagina ? `, pág. ${ficha.pagina}` : ''}
            </p>
          </>
        )}
      </div>

      {revelada ? (
        <div className="repaso__acciones">
          <button type="button" className="btn btn--fallo" onClick={() => responder('mal')}>
            No me acordaba
          </button>
          <button type="button" className="btn btn--acierto" onClick={() => responder('bien')}>
            Lo sabía
          </button>
        </div>
      ) : (
        <div className="repaso__acciones">
          <button type="button" className="btn btn--primario" onClick={() => setRevelada(true)}>
            Mostrar respuesta
          </button>
        </div>
      )}
    </section>
  )
}
