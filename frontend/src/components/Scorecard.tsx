import { useEffect, useRef } from 'react'
import type { EvaluacionClinica } from '../types'

interface Props {
  evaluacion: EvaluacionClinica
  onCerrar: () => void
  onNuevaSesion: () => void
}

function nivel(puntaje: number) {
  if (puntaje >= 80) return 'alto'
  if (puntaje >= 60) return 'medio'
  return 'bajo'
}

export function Scorecard({ evaluacion, onCerrar, onNuevaSesion }: Props) {
  const dialogoRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    dialogoRef.current?.focus()
    const alPresionar = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCerrar()
    }
    window.addEventListener('keydown', alPresionar)
    return () => window.removeEventListener('keydown', alPresionar)
  }, [onCerrar])

  const { puntaje_total } = evaluacion

  return (
    <div className="overlay" onClick={onCerrar}>
      <div
        className="scorecard"
        role="dialog"
        aria-modal="true"
        aria-labelledby="scorecard-titulo"
        tabIndex={-1}
        ref={dialogoRef}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="scorecard__header">
          <div>
            <p className="scorecard__kicker">Evaluación del tutor</p>
            <h2 id="scorecard-titulo">Scorecard de la sesión</h2>
          </div>
          <div className={`puntaje puntaje--${nivel(puntaje_total)}`}>
            <span className="puntaje__valor">{puntaje_total}</span>
            <span className="puntaje__total">/100</span>
          </div>
        </header>

        <div className="scorecard__cuerpo">
          <section>
            <h3>Razonamiento diagnóstico</h3>
            <p>{evaluacion.razonamiento_diagnostico}</p>
          </section>

          <section>
            <h3>Costo-efectividad</h3>
            <p>{evaluacion.costo_efectividad}</p>
          </section>

          <section>
            <h3>Pruebas innecesarias</h3>
            {evaluacion.pruebas_innecesarias.length === 0 ? (
              <p className="vacio">Ninguna. Buen uso de recursos.</p>
            ) : (
              <ul className="lista lista--aviso">
                {evaluacion.pruebas_innecesarias.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h3>Errores críticos</h3>
            {evaluacion.errores_criticos.length === 0 ? (
              <p className="vacio">Sin errores críticos.</p>
            ) : (
              <ul className="lista lista--critico">
                {evaluacion.errores_criticos.map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            )}
          </section>

          {evaluacion.retroalimentacion && (
            <section className="scorecard__feedback">
              <h3>Retroalimentación</h3>
              <p>{evaluacion.retroalimentacion}</p>
            </section>
          )}
        </div>

        <footer className="scorecard__footer">
          <button type="button" className="btn btn--secundario" onClick={onCerrar}>
            Volver a la transcripción
          </button>
          <button type="button" className="btn btn--primario" onClick={onNuevaSesion}>
            Nuevo caso
          </button>
        </footer>
      </div>
    </div>
  )
}
