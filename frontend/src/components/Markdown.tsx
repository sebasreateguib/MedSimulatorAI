import { Fragment, type ReactNode } from 'react'
import { analizarBloques, analizarInline, pareceMarkdown, type ItemLista } from '../lib/markdown'
import type { CitaMaterial } from '../types'

interface Props {
  texto: string
  /**
   * Citas que respaldan la respuesta. Con ellas, las marcas `[n]` del texto se
   * vuelven botones; sin ellas quedan como texto, que es lo correcto mientras
   * el stream todavía no entregó la lista.
   */
  citas?: CitaMaterial[]
  onAbrirCita?: (cita: CitaMaterial) => void
}

/** Renderiza markdown con el sistema visual de la app (ver lib/markdown.ts). */
export function Markdown({ texto, citas = [], onAbrirCita }: Props) {
  // Texto sin marcas: se devuelve tal cual, conservando los saltos de línea.
  // Envolver el habla del paciente en párrafos no ordena nada y le cambia el ritmo.
  if (!pareceMarkdown(texto)) {
    return <>{texto}</>
  }

  const bloques = analizarBloques(texto)

  return (
    <div className="md">
      {bloques.map((bloque, i) => {
        switch (bloque.tipo) {
          case 'encabezado': {
            const Etiqueta = `h${bloque.nivel + 2}` as 'h3' | 'h4' | 'h5'
            return (
              <Etiqueta key={i} className={`md__h md__h--${bloque.nivel}`}>
                <Inline texto={bloque.texto} citas={citas} onAbrirCita={onAbrirCita} />
              </Etiqueta>
            )
          }

          case 'lista':
            return <Lista key={i} {...bloque} citas={citas} onAbrirCita={onAbrirCita} />

          case 'cita':
            return (
              <blockquote key={i} className="md__cita">
                {bloque.lineas.map((linea, j) => (
                  <p key={j}>
                    <Inline texto={linea} citas={citas} onAbrirCita={onAbrirCita} />
                  </p>
                ))}
              </blockquote>
            )

          case 'codigo':
            return (
              <pre key={i} className="md__codigo">
                <code>{bloque.texto}</code>
              </pre>
            )

          case 'tabla':
            return (
              // La tabla scrollea dentro de su caja: una de seis columnas no
              // puede ensanchar la burbuja y romper el ancho de la conversación.
              <div key={i} className="md__tabla-caja">
                <table className="md__tabla">
                  <thead>
                    <tr>
                      {bloque.encabezados.map((celda, j) => (
                        <th key={j}>
                          <Inline texto={celda} citas={citas} onAbrirCita={onAbrirCita} />
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {bloque.filas.map((fila, j) => (
                      <tr key={j}>
                        {fila.map((celda, k) => (
                          <td key={k}>
                            <Inline texto={celda} citas={citas} onAbrirCita={onAbrirCita} />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )

          case 'regla':
            return <hr key={i} className="md__regla" />

          default:
            return (
              <p key={i} className="md__p">
                <Inline texto={bloque.texto} citas={citas} onAbrirCita={onAbrirCita} />
              </p>
            )
        }
      })}
    </div>
  )
}

interface PropsLista {
  ordenada: boolean
  items: ItemLista[]
  citas: CitaMaterial[]
  onAbrirCita?: (cita: CitaMaterial) => void
}

/** Agrupa los items sangrados dentro del item de primer nivel que los precede. */
function Lista({ ordenada, items, citas, onAbrirCita }: PropsLista) {
  const Etiqueta = ordenada ? 'ol' : 'ul'
  const grupos: { item: ItemLista; hijos: ItemLista[] }[] = []

  for (const item of items) {
    if (item.nivel === 0 || grupos.length === 0) {
      grupos.push({ item, hijos: [] })
    } else {
      grupos[grupos.length - 1].hijos.push(item)
    }
  }

  return (
    <Etiqueta className="md__lista">
      {grupos.map((grupo, i) => (
        <li key={i}>
          <Inline texto={grupo.item.texto} citas={citas} onAbrirCita={onAbrirCita} />
          {grupo.hijos.length > 0 && (
            <Etiqueta className="md__lista md__lista--anidada">
              {grupo.hijos.map((hijo, j) => (
                <li key={j}>
                  <Inline texto={hijo.texto} citas={citas} onAbrirCita={onAbrirCita} />
                </li>
              ))}
            </Etiqueta>
          )}
        </li>
      ))}
    </Etiqueta>
  )
}

interface PropsInline {
  texto: string
  citas: CitaMaterial[]
  onAbrirCita?: (cita: CitaMaterial) => void
}

function Inline({ texto, citas, onAbrirCita }: PropsInline): ReactNode {
  return (
    <>
      {analizarInline(texto).map((trozo, i) => {
        switch (trozo.tipo) {
          case 'fuerte':
            return <strong key={i}>{trozo.texto}</strong>
          case 'enfasis':
            return <em key={i}>{trozo.texto}</em>
          case 'codigo':
            return (
              <code key={i} className="md__code">
                {trozo.texto}
              </code>
            )
          case 'enlace':
            return (
              // Enlace a un dominio cualquiera que escribió un modelo: sin
              // `noreferrer` la página destino recibe de dónde vino el clic.
              <a key={i} href={trozo.url} target="_blank" rel="noopener noreferrer">
                {trozo.texto}
              </a>
            )
          case 'cita': {
            const cita = citas.find((c) => c.n === trozo.n)
            if (!cita || !onAbrirCita) return <Fragment key={i}>[{trozo.n}]</Fragment>
            return (
              <button
                key={i}
                type="button"
                className="cita-marca mono"
                onClick={() => onAbrirCita(cita)}
                title={`${cita.fuente}${cita.pagina ? `, pág. ${cita.pagina}` : ''}`}
              >
                {trozo.n}
              </button>
            )
          }
          default:
            return <Fragment key={i}>{trozo.texto}</Fragment>
        }
      })}
    </>
  )
}
