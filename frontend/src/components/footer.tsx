import type { CSSProperties } from 'react'
import { Marca } from './Marca'

/**
 * Colofón de la lámina: el pie del landing.
 *
 * Conserva la estructura con la que llegó el componente —bloque de marca a la
 * izquierda, columnas de enlaces a la derecha, firma calada al pie— pero sin
 * `motion`: la aparición escalonada la resuelve el mismo `[data-revelar]` que
 * usa el resto de la página, con un retraso por columna. Una librería de
 * animación entera para cuatro columnas no se paga.
 *
 * Los datos son los de este proyecto, no los del template: las secciones de la
 * lámina, el corpus que indexa el RAG, los proveedores de `config/agents.yaml`
 * y el repositorio.
 */

const REPO = 'https://github.com/sebasreateguib/MedSimulatorAI'

interface Enlace {
  texto: string
  url: string
  /** Solo el índice de la lámina: repite la numeración de las secciones. */
  n?: string
}

export interface ColumnaColofon {
  rotulo: string
  enlaces: Enlace[]
}

const COLUMNAS: ColumnaColofon[] = [
  {
    rotulo: 'Lámina',
    enlaces: [
      { n: 'I', texto: 'Procedimiento', url: '#procedimiento' },
      { n: 'II', texto: 'Agentes', url: '#agentes' },
      { n: 'III', texto: 'Antialucinación', url: '#antialucinacion' },
      { n: 'IV', texto: 'Tecnologías', url: '#tecnologias' },
      { n: 'V', texto: 'Costos', url: '#costos' },
    ],
  },
  {
    rotulo: 'Corpus',
    enlaces: [
      { texto: 'Guías de práctica clínica', url: 'https://www.escardio.org/Guidelines' },
      { texto: 'PubMed Open Access', url: 'https://pmc.ncbi.nlm.nih.gov/tools/openftlist/' },
      { texto: 'openFDA', url: 'https://open.fda.gov/' },
    ],
  },
  {
    rotulo: 'Modelos',
    enlaces: [
      { texto: 'Anthropic · Opus 5', url: 'https://www.anthropic.com' },
      { texto: 'Groq · Llama 3.3', url: 'https://groq.com' },
      { texto: 'OpenRouter · DeepSeek', url: 'https://openrouter.ai' },
    ],
  },
  {
    rotulo: 'Proyecto',
    enlaces: [
      { texto: 'Código', url: REPO },
      { texto: 'Licencia MIT', url: `${REPO}/blob/main/LICENSE` },
      { texto: 'Reportar un problema', url: `${REPO}/issues` },
    ],
  },
]

const AVISO =
  'Material de estudio. No sustituye criterio clínico ni sirve para decidir sobre pacientes reales.'

interface Props {
  bajada?: string
  columnas?: ColumnaColofon[]
  aviso?: string
  legal?: string
  className?: string
}

export function Footer({
  bajada = 'Entrenamiento en razonamiento clínico',
  columnas = COLUMNAS,
  aviso = AVISO,
  legal = '© 2026',
  className,
}: Props) {
  return (
    <footer className={className ? `colofon ${className}` : 'colofon'}>
      {/* Una sola retícula para las cinco columnas: la de marca es una más y no
          un bloque aparte que se lleve un tercio del ancho para una línea. El
          aviso vive acá y no en el pie, que es lo que le da altura a la columna
          y empareja el bloque con el índice de la lámina. */}
      <div className="colofon__cuerpo">
        <div className="colofon__titulo" data-revelar>
          {/* Sin el nombre al lado, la marca pasa de dibujo a contenido. */}
          <Marca size={40} titulo="MedSimulator AI" />
          <p className="colofon__bajada">{bajada}</p>
          <p className="colofon__aviso">{aviso}</p>
        </div>

        {columnas.map((columna, i) => (
          <nav
            key={columna.rotulo}
            className="colofon__columna"
            aria-label={columna.rotulo}
            data-revelar
            // Las columnas entran una detrás de otra, como el stagger del
            // componente original. El retraso viaja por custom property
            // porque quien lo consume es la transición de [data-revelar].
            style={{ '--retraso': `${i * 90}ms` } as CSSProperties}
          >
            <p className="colofon__rotulo">{columna.rotulo}</p>
            <ul className="colofon__lista">
              {columna.enlaces.map((enlace) => {
                const interno = enlace.url.startsWith('#')
                return (
                  <li key={enlace.url}>
                    <a
                      className="colofon__enlace"
                      href={enlace.url}
                      // Los anclas de la lámina se quedan en la página; el
                      // resto son sitios de terceros y se abren aparte.
                      target={interno ? undefined : '_blank'}
                      rel={interno ? undefined : 'noreferrer'}
                    >
                      {enlace.n && (
                        <span className="colofon__n" aria-hidden="true">
                          {enlace.n}
                        </span>
                      )}
                      {enlace.texto}
                    </a>
                  </li>
                )
              })}
            </ul>
          </nav>
        ))}
      </div>

      <p className="colofon__legal">{legal}</p>

      {/* Firma calada: cierra la lámina con la marca en gran cuerpo, en
          contorno para que no pese más que el contenido. Decorativa —el
          nombre ya se anunció arriba—, así que no se lee dos veces. */}
      <p className="colofon__firma" aria-hidden="true" data-revelar>
        MedSimulator
      </p>
    </footer>
  )
}

export default Footer
