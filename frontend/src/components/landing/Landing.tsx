import { EstadoBackend } from '../EstadoBackend'
import { useRevelado } from '../../hooks/useRevelado'
import { useCabecera } from '../../hooks/useCabecera'
import { CursorSeguidor } from './CursorSeguidor'
import { DiagramaFlujo } from './DiagramaFlujo'
import { Hero } from './Hero'
import '../../styles/landing.css'

const PASOS = [
  {
    n: 'I',
    titulo: 'Anamnesis',
    texto:
      'El paciente responde según su historia oculta, sus síntomas y su estado emocional. No revela el diagnóstico: hay que saber preguntar.',
    margen: 'Groq · 70B',
  },
  {
    n: 'II',
    titulo: 'Estudios e interconsultas',
    texto:
      'Laboratorio, imágenes, o llamar al cardiólogo. Cada herramienta corre como tool call sobre los datos precargados del caso.',
    margen: 'tool_use',
  },
  {
    n: 'III',
    titulo: 'Validación contra el corpus',
    texto:
      'Cada dosis y cada criterio se verifica contra las guías antes de darse por bueno, con el texto literal citado y la página exacta.',
    margen: 'citations',
  },
  {
    n: 'IV',
    titulo: 'Scorecard con rúbrica',
    texto:
      'Al cerrar, el tutor devuelve puntaje, razonamiento diagnóstico, costo-efectividad, pruebas innecesarias y errores críticos.',
    margen: 'async',
  },
]

const AGENTES = [
  {
    nombre: 'Paciente',
    proveedor: 'Groq',
    modelo: 'llama-3.3-70b',
    porque: 'El agente con más turnos y el único donde la latencia es parte de la experiencia.',
  },
  {
    nombre: 'Router',
    proveedor: 'Groq',
    modelo: 'llama-3.1-8b',
    porque: 'Clasificación de intención en milisegundos, a costo casi nulo.',
  },
  {
    nombre: 'Especialista',
    proveedor: 'OpenRouter',
    modelo: 'deepseek-chat',
    porque: 'Razona sobre hallazgos ya descritos en texto; alcanza un modelo intermedio.',
  },
  {
    nombre: 'Validador',
    proveedor: 'Anthropic',
    modelo: 'claude-opus-5',
    porque: 'El punto donde una alucinación es peligrosa. Acá no se escatima.',
    critico: true,
  },
  {
    nombre: 'Tutor',
    proveedor: 'Anthropic',
    modelo: 'claude-opus-5',
    porque: 'Corre fuera del loop síncrono: la latencia no importa y no encarece cada turno.',
  },
]

/**
 * Stack real, tomado de requirements.txt, pyproject.toml, docker-compose.yml
 * y package.json. Solo nombres: el porqué de cada elección está en § III.
 */
const STACK = [
  {
    n: '01',
    capa: 'API',
    principal: 'FastAPI',
    resto: ['Python 3.10+', 'Uvicorn', 'Pydantic', 'pydantic-settings', 'httpx'],
    tono: 'oxido',
  },
  {
    n: '02',
    capa: 'Modelos',
    principal: 'Anthropic',
    resto: ['openai SDK', 'Groq', 'OpenRouter'],
    tono: 'ambar',
  },
  {
    n: '03',
    capa: 'Datos',
    principal: 'PostgreSQL',
    resto: ['pgvector', 'SQLAlchemy', 'asyncpg', 'Alembic'],
    tono: 'verde',
  },
  {
    n: '04',
    capa: 'RAG',
    principal: 'Docling',
    resto: ['sentence-transformers', 'bge-m3', 'FlagEmbedding', 'rank-bm25'],
    tono: 'oxido',
  },
  {
    n: '05',
    capa: 'Cliente',
    principal: 'React',
    resto: ['TypeScript', 'Vite', 'ogl', 'SSE'],
    tono: 'ambar',
  },
  {
    n: '06',
    capa: 'Operación',
    principal: 'Docker',
    resto: ['Langfuse', 'pytest', 'pytest-asyncio', 'oxlint'],
    tono: 'verde',
  },
]

interface Props {
  onEntrar: () => void
}

export function Landing({ onEntrar }: Props) {
  useRevelado()
  const { topeRef, centinelaRef, enTope, sobrePlaca } = useCabecera()

  const clasesNav = [
    'landing__nav',
    sobrePlaca ? 'landing__nav--placa' : '',
    enTope && sobrePlaca ? 'landing__nav--tope' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className="landing">
      <CursorSeguidor />
      <div ref={topeRef} className="centinela-tope" aria-hidden="true" />

      <header className={clasesNav}>
        <div className="topbar__marca">
          <span className="logo" aria-hidden="true" />
          <div>
            <h2>MedSimulator&nbsp;AI</h2>
            <p>Entrenamiento en razonamiento clínico</p>
          </div>
        </div>
        <div className="landing__nav-acciones">
          <EstadoBackend />
          <button type="button" className="btn btn--primario" onClick={onEntrar}>
            Iniciar sesión
          </button>
        </div>
      </header>

      <Hero onEntrar={onEntrar} />

      {/* Centinela: marca dónde termina la lámina para que la cabecera se invierta. */}
      <div ref={centinelaRef} aria-hidden="true" />

      <main className="landing__cuerpo">
        {/* § I ── Procedimiento */}
        <section id="procedimiento" className="seccion">
          <header className="seccion__cabecera" data-revelar>
            <p className="seccion__marca">§ I</p>
            <h2 className="seccion__titulo">Cuatro momentos de una consulta</h2>
            <p className="seccion__bajada">
              La competencia que el simulador enseña no es reconocer un cuadro escrito: es
              construirlo pregunta por pregunta y sostener el razonamiento cuando el paciente
              esconde lo importante.
            </p>
          </header>

          <ol className="pasos">
            {PASOS.map((paso) => (
              <li key={paso.n} className="paso" data-revelar>
                <span className="paso__n">{paso.n}</span>
                <div className="paso__cuerpo">
                  <h3>{paso.titulo}</h3>
                  <p>{paso.texto}</p>
                </div>
                <span className="paso__margen">{paso.margen}</span>
              </li>
            ))}
          </ol>
        </section>

        {/* § II ── Recorrido de un turno (diagrama) */}
        <section id="recorrido" className="seccion seccion--tono">
          <header className="seccion__cabecera" data-revelar>
            <p className="seccion__marca">§ II</p>
            <h2 className="seccion__titulo">Qué pasa entre la pregunta y la respuesta</h2>
            <p className="seccion__bajada">
              Un router barato clasifica la intención y deriva. Lo que el estudiante ordena pasa por
              validación antes de volver. El tutor no está en el camino: escucha en paralelo, así
              ningún turno paga su latencia.
            </p>
          </header>

          <DiagramaFlujo />
        </section>

        {/* § III ── Agentes */}
        <section className="seccion">
          <header className="seccion__cabecera" data-revelar>
            <p className="seccion__marca">§ III</p>
            <h2 className="seccion__titulo">Cinco agentes, tres proveedores, un motivo cada uno</h2>
            <p className="seccion__bajada">
              El modelo se elige por trabajo, no por marca: velocidad donde se nota, verificación
              donde una alucinación es peligrosa. Cambiar de proveedor es editar una línea de{' '}
              <code>config/agents.yaml</code>.
            </p>
          </header>

          <div className="tabla-envoltura" data-revelar>
            <table className="tabla">
              <thead>
                <tr>
                  <th scope="col">Agente</th>
                  <th scope="col">Proveedor</th>
                  <th scope="col">Modelo</th>
                  <th scope="col">Por qué</th>
                </tr>
              </thead>
              <tbody>
                {AGENTES.map((agente) => (
                  <tr key={agente.nombre} className={agente.critico ? 'tabla__critico' : undefined}>
                    <th scope="row">{agente.nombre}</th>
                    <td className="tabla__mono">{agente.proveedor}</td>
                    <td className="tabla__mono">{agente.modelo}</td>
                    <td>{agente.porque}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* § IV ── Antialucinación */}
        <section className="seccion">
          <div className="destacado">
            <header className="seccion__cabecera" data-revelar>
              <p className="seccion__marca">§ IV</p>
              <h2 className="seccion__titulo">La cita no se pide: se impone</h2>
              <p className="seccion__bajada">
                Citar la fuente no es una instrucción en el prompt, es una restricción del
                decodificador. Cada afirmación llega con el texto literal del documento y su página,
                así un error de parsing se vuelve auditable en vez de invisible.
              </p>
            </header>

            <figure className="cita" data-revelar>
              <span className="sello" aria-hidden="true">
                Verificado
              </span>
              <blockquote>
                En fibrilación auricular con respuesta ventricular rápida, el control inicial de
                frecuencia se realiza con betabloqueantes o calcioantagonistas no
                dihidropiridínicos.
              </blockquote>
              <figcaption>
                Guía ESC de fibrilación auricular — p.&nbsp;42
                <span className="cita__estado">cita literal hallada en el chunk</span>
              </figcaption>
            </figure>
          </div>
        </section>

        {/* § V ── Tecnologías */}
        <section id="tecnologias" className="seccion seccion--tono">
          <header className="seccion__cabecera" data-revelar>
            <p className="seccion__marca">§ V</p>
            <h2 className="seccion__titulo">Tecnologías</h2>
          </header>

          <div className="stack-marco" data-revelar>
            <div className="stack-scroll">
              <ol className="stack">
                {STACK.map((capa) => (
                  <li key={capa.n} className={`tec tec--${capa.tono}`}>
                    <p className="tec__n">
                      <span>{capa.n}</span>
                    </p>
                    <p className="tec__capa">{capa.capa}</p>
                    <h3 className="tec__principal">{capa.principal}</h3>
                    <ul className="tec__resto">
                      {capa.resto.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </section>

        {/* § VI ── Costos */}
        <section className="seccion">
          <header className="seccion__cabecera" data-revelar>
            <p className="seccion__marca">§ VI</p>
            <h2 className="seccion__titulo">Cuarenta centavos por sesión de veinte minutos</h2>
            <p className="seccion__bajada">
              Tres caminos posibles para las mismas sesenta vueltas de conversación. El elegido no es
              el más barato: es el que pone el modelo caro exactamente donde equivocarse duele.
            </p>
          </header>

          <div className="costos">
            <article className="costo" data-revelar>
              <p className="costo__monto">1.35</p>
              <p className="costo__label">Todo Anthropic</p>
              <p className="costo__nota">Máxima calidad, usado como baseline de comparación.</p>
            </article>
            <article className="costo costo--elegido" data-revelar>
              <p className="costo__monto">0.40</p>
              <p className="costo__label">Híbrido · elegido</p>
              <p className="costo__nota">
                Groq para el volumen de turnos, Anthropic donde una alucinación duele.
              </p>
            </article>
            <article className="costo" data-revelar>
              <p className="costo__monto">0.14</p>
              <p className="costo__label">Todo abierto</p>
              <p className="costo__nota">10× más barato, sin verificación con citations nativas.</p>
            </article>
          </div>
        </section>
      </main>

      {/* Cierre: vuelve la placa oscura, como bookend del hero. */}
      <section className="cierre">
        <p className="placa__rotulo">Caso disponible</p>
        <h2>
          Fibrilación auricular aguda.
          <br />
          <em>68 años, palpitaciones, angustia.</em>
        </h2>
        <p className="cierre__texto">
          El desencadenante está en la historia. El paciente no lo va a mencionar solo.
        </p>
        <button type="button" className="btn btn--luz btn--grande" onClick={onEntrar}>
          Entrar al simulador
        </button>
      </section>

      <footer className="landing__footer">
        <span className="landing__footer-marca">MedSimulator&nbsp;AI</span>
        <span>Guías públicas · PubMed OA · openFDA</span>
      </footer>
    </div>
  )
}
