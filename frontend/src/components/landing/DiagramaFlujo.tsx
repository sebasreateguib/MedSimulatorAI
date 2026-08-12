import { useEsAngosto } from '../../hooks/useEsAngosto'

interface NodoProps {
  x: number
  y: number
  w: number
  h?: number
  n: string
  nombre: string
  sub: string
  variante?: 'critico' | 'async'
  /** Reduce el nombre cuando el nodo es angosto. */
  compacto?: boolean
}

function Nodo({ x, y, w, h = 74, n, nombre, sub, variante, compacto }: NodoProps) {
  const clase = [
    'dg-nodo',
    variante ? `dg-nodo--${variante}` : '',
    compacto ? 'dg-nodo--compacto' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <g className={clase}>
      <rect className="dg-caja" x={x} y={y} width={w} height={h} rx="2" />
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

const NODOS = [
  { n: '01', nombre: 'Estudiante', sub: 'turno' },
  { n: '02', nombre: 'Router', sub: 'Groq · Llama 3.1 8B' },
  { n: '03', nombre: 'Paciente', sub: 'Groq · Llama 3.3 70B' },
  { n: '04', nombre: 'Especialista', sub: 'OpenRouter · DeepSeek V3' },
  { n: '05', nombre: 'Acción clínica', sub: 'tool_use' },
  { n: '06', nombre: 'Validador', sub: 'Opus 5 · citations' },
] as const

const DESCRIPCION =
  'El mensaje del estudiante pasa por un router de intención que lo deriva al paciente virtual, a un especialista o a una acción clínica. Las acciones clínicas se validan contra el corpus documental antes de volver al estudiante. El tutor escucha el stream en paralelo, fuera del loop síncrono.'

function Marcadores() {
  return (
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
  )
}

/** Recorrido en fila: el router abre tres ramas en paralelo hacia la derecha. */
function Horizontal() {
  return (
    <svg className="diagrama" viewBox="0 0 1000 516" role="img" aria-labelledby="dg-tit dg-desc">
      <title id="dg-tit">Recorrido de un turno</title>
      <desc id="dg-desc">{DESCRIPCION}</desc>
      <Marcadores />

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
      <path
        className="dg-pulso"
        d="M214 233 H262 M458 233 H482 V353 H506 M722 353 H750 M956 353 H984 V24 H119 V186"
      />

      <path className="dg-via dg-via--async" d="M617 390 V426" />
      <path className="dg-via dg-via--async" d="M871 390 V426" />

      <text className="dg-etiqueta dg-etiqueta--oxido" x="551" y="16">
        respuesta verificada
      </text>
      <text className="dg-etiqueta" x="744" y="414" textAnchor="middle">
        escucha el stream
      </text>

      <Nodo x={24} y={196} w={190} {...NODOS[0]} />
      <Nodo x={268} y={196} w={190} {...NODOS[1]} />
      <Nodo x={512} y={76} w={210} {...NODOS[2]} />
      <Nodo x={512} y={196} w={210} {...NODOS[3]} />
      <Nodo x={512} y={316} w={210} {...NODOS[4]} />
      <Nodo x={756} y={316} w={200} {...NODOS[5]} variante="critico" />
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
  )
}

/**
 * Recorrido en columna, para pantallas angostas.
 *
 * No es el diagrama horizontal escalado: a 375px de ancho, ese viewBox de
 * 1000 dejaría los nombres en 7px. Las ramas del router siguen siendo
 * paralelas —el bus baja por el canal izquierdo y entra por el costado— para
 * no sugerir una secuencia que no existe.
 */
function Vertical() {
  return (
    <svg
      className="diagrama diagrama--vertical"
      viewBox="0 0 380 812"
      role="img"
      aria-labelledby="dgv-tit dgv-desc"
    >
      <title id="dgv-tit">Recorrido de un turno</title>
      <desc id="dgv-desc">{DESCRIPCION}</desc>
      <Marcadores />

      <path className="dg-via" d="M192 96 V132" markerEnd="url(#flecha)" />
      <path className="dg-via" d="M192 208 V226 M22 226 H192 M22 226 V510" />
      <path className="dg-via" d="M22 286 H46" markerEnd="url(#flecha)" />
      <path className="dg-via" d="M22 398 H46" markerEnd="url(#flecha)" />
      <path className="dg-via" d="M22 510 H46" markerEnd="url(#flecha)" />
      <path className="dg-via" d="M192 544 V580" markerEnd="url(#flecha)" />
      <path
        className="dg-via dg-via--oxido"
        d="M332 622 H358 V14 H192 V22"
        markerEnd="url(#flecha-oxido)"
      />
      <path
        className="dg-pulso"
        d="M192 96 V132 M192 208 V226 H22 V510 H46 M192 544 V580 M332 622 H358 V14 H192 V22"
      />

      <path className="dg-via dg-via--async" d="M192 656 V706" />
      <text className="dg-etiqueta" x="202" y="686">
        escucha el stream
      </text>
      <text
        className="dg-etiqueta dg-etiqueta--oxido"
        transform="rotate(-90 346 330)"
        x="346"
        y="330"
        textAnchor="middle"
      >
        respuesta verificada
      </text>

      <Nodo x={52} y={28} w={280} h={68} {...NODOS[0]} compacto />
      <Nodo x={52} y={140} w={280} h={68} {...NODOS[1]} compacto />
      <Nodo x={52} y={252} w={280} h={68} {...NODOS[2]} compacto />
      <Nodo x={52} y={364} w={280} h={68} {...NODOS[3]} compacto />
      <Nodo x={52} y={476} w={280} h={68} {...NODOS[4]} compacto />
      <Nodo x={52} y={588} w={280} h={68} {...NODOS[5]} variante="critico" compacto />
      <Nodo
        x={52}
        y={706}
        w={280}
        h={68}
        n="07"
        nombre="Tutor"
        sub="async · scorecard al cerrar"
        variante="async"
        compacto
      />
    </svg>
  )
}

export function DiagramaFlujo() {
  const angosto = useEsAngosto()

  return (
    <figure className="diagrama-envoltura" data-revelar>
      <div className="diagrama-scroll">{angosto ? <Vertical /> : <Horizontal />}</div>
    </figure>
  )
}
