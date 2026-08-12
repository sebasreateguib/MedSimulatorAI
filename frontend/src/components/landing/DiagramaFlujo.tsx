interface NodoProps {
  x: number
  y: number
  w: number
  n: string
  nombre: string
  sub: string
  variante?: 'critico' | 'async'
}

const ALTO = 74

function Nodo({ x, y, w, n, nombre, sub, variante }: NodoProps) {
  const clase = variante ? `dg-nodo dg-nodo--${variante}` : 'dg-nodo'
  return (
    <g className={clase}>
      <rect className="dg-caja" x={x} y={y} width={w} height={ALTO} rx="2" />
      <text className="dg-indice" x={x + 18} y={y + 23}>
        {n}
      </text>
      <text className="dg-nombre" x={x + 18} y={y + 46}>
        {nombre}
      </text>
      <text className="dg-sub" x={x + 18} y={y + 63}>
        {sub}
      </text>
    </g>
  )
}

/**
 * Recorrido de un turno.
 *
 * Va sobre lámina oscura como el hero: el trazo fino en hueso tiene mucho más
 * contraste que en tinta sobre papel, y el camino crítico en óxido se lee de
 * un vistazo. El pulso animado recorre el circuito completo en un solo path.
 */
export function DiagramaFlujo() {
  return (
    <figure className="diagrama-envoltura" data-revelar>
      <div className="diagrama-scroll">
        <svg className="diagrama" viewBox="0 0 1000 516" role="img" aria-labelledby="dg-tit dg-desc">
          <title id="dg-tit">Recorrido de un turno</title>
          <desc id="dg-desc">
            El mensaje del estudiante pasa por un router de intención que lo deriva al paciente
            virtual, a un especialista o a una acción clínica. Las acciones clínicas se validan
            contra el corpus documental antes de volver al estudiante. El tutor escucha el stream
            en paralelo, fuera del loop síncrono.
          </desc>

          <defs>
            <marker
              id="flecha"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="5"
              markerHeight="5"
              orient="auto"
            >
              <path className="dg-flecha" d="M0 0 10 5 0 10z" />
            </marker>
            <marker
              id="flecha-oxido"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="5"
              markerHeight="5"
              orient="auto"
            >
              <path className="dg-flecha dg-flecha--oxido" d="M0 0 10 5 0 10z" />
            </marker>
          </defs>

          {/* Estructura del circuito */}
          <path className="dg-via" d="M214 233 H262" markerEnd="url(#flecha)" />
          <path className="dg-via" d="M458 233 H482 M482 113 V353" />
          <path className="dg-via" d="M482 113 H506" markerEnd="url(#flecha)" />
          <path className="dg-via" d="M482 233 H506" markerEnd="url(#flecha)" />
          <path className="dg-via" d="M482 353 H506" markerEnd="url(#flecha)" />
          <path className="dg-via" d="M722 353 H750" markerEnd="url(#flecha)" />
          <path
            className="dg-via dg-via--oxido"
            d="M956 353 H984 V24 H119 V186"
            markerEnd="url(#flecha-oxido)"
          />

          {/* Pulso: un solo path recorre el circuito entero */}
          <path
            className="dg-pulso"
            d="M214 233 H262 M458 233 H482 V353 H506 M722 353 H750 M956 353 H984 V24 H119 V186"
          />

          {/* Escucha asíncrona */}
          <path className="dg-via dg-via--async" d="M617 390 V426" />
          <path className="dg-via dg-via--async" d="M871 390 V426" />

          <text className="dg-etiqueta dg-etiqueta--oxido" x="551" y="16">
            respuesta verificada
          </text>
          <text className="dg-etiqueta" x="744" y="414" textAnchor="middle">
            escucha el stream
          </text>

          <Nodo x={24} y={196} w={190} n="01" nombre="Estudiante" sub="turno" />
          <Nodo x={268} y={196} w={190} n="02" nombre="Router" sub="Groq · Llama 3.1 8B" />
          <Nodo x={512} y={76} w={210} n="03" nombre="Paciente" sub="Groq · Llama 3.3 70B" />
          <Nodo x={512} y={196} w={210} n="04" nombre="Especialista" sub="OpenRouter · DeepSeek V3" />
          <Nodo x={512} y={316} w={210} n="05" nombre="Acción clínica" sub="tool_use" />
          <Nodo
            x={756}
            y={316}
            w={200}
            n="06"
            nombre="Validador"
            sub="Opus 5 · citations"
            variante="critico"
          />
          <Nodo
            x={24}
            y={426}
            w={932}
            n="07"
            nombre="Tutor"
            sub="async · fuera del loop síncrono · scorecard con rúbrica al cerrar"
            variante="async"
          />
        </svg>
      </div>
    </figure>
  )
}
