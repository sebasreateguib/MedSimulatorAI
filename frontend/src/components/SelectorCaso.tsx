import { useEffect, useState } from 'react'
import { listarCasos } from '../lib/api'
import type { Caso } from '../types'

interface Props {
  onSeleccionar: (caso: Caso) => void
  cargando: boolean
}

export function SelectorCaso({ onSeleccionar, cargando }: Props) {
  const [casos, setCasos] = useState<Caso[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let vigente = true
    listarCasos().then(
      (c) => vigente && setCasos(c),
      (err) => {
        if (!vigente) return
        // Sin catálogo no hay nada que ofrecer: mostrar el motivo es mejor que
        // dejar dos esqueletos girando para siempre.
        setError(err instanceof Error ? err.message : 'No se pudo cargar el catálogo de casos.')
        setCasos([])
      },
    )
    return () => {
      vigente = false
    }
  }, [])

  return (
    <section className="selector">
      <div className="selector__intro">
        <h2>Elegí un caso clínico</h2>
        <p>
          No vas a leer el caso: lo vas a interrogar. El paciente responde según su historia
          oculta y no revela el diagnóstico. Al cerrar la sesión, el tutor evalúa tu razonamiento.
        </p>
      </div>

      {error && (
        <div className="alerta" role="alert">
          <span>{error}</span>
        </div>
      )}

      {!error && casos !== null && casos.length === 0 && (
        <p className="vacio">
          No hay casos clínicos cargados. Agregá un archivo YAML en config/casos/ y volvé a entrar.
        </p>
      )}

      {casos === null ? (
        <div className="selector__grid">
          {[0, 1].map((i) => (
            <div key={i} className="caso caso--skeleton" aria-hidden="true" />
          ))}
        </div>
      ) : (
        <ul className="selector__grid">
          {casos.map((caso) => (
            <li key={caso.id}>
              <button
                className="caso"
                onClick={() => onSeleccionar(caso)}
                disabled={cargando}
                type="button"
              >
                <span className={`badge badge--${caso.dificultad}`}>{caso.dificultad}</span>
                <h3>{caso.titulo}</h3>
                <p className="caso__paciente">
                  {caso.paciente.nombre} · {caso.paciente.edad} años · {caso.paciente.genero}
                </p>
                <p className="caso__motivo">{caso.motivo_consulta}</p>
                <span className="caso__cta">{cargando ? 'Iniciando…' : 'Iniciar sesión →'}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
