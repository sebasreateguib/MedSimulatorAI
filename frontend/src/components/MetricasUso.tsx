import { useEffect, useMemo, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import * as api from '../lib/api'
import { preferenciaDemo, sesionesDemo } from '../lib/demo'
import type { SesionHistorial } from '../types'

type Estado = 'cargando' | 'listo' | 'error'

/**
 * Bandas de desempeño. Son el eje de casi todo el tablero —distribución,
 * series, insignias— así que viven en un solo lugar: mover un umbral acá
 * mueve el tablero entero y nada queda desfasado.
 */
const BANDAS = [
  { id: 'alto', rotulo: 'Alto', min: 80, color: 'var(--verde)' },
  { id: 'medio', rotulo: 'Medio', min: 60, color: 'var(--ambar)' },
  { id: 'bajo', rotulo: 'Bajo', min: 0, color: 'var(--oxido)' },
] as const

type BandaId = (typeof BANDAS)[number]['id']

function bandaDe(puntaje: number) {
  return BANDAS.find((b) => puntaje >= b.min) ?? BANDAS[BANDAS.length - 1]
}

/** Lunes primero: el `getDay()` de JS arranca en domingo y descoloca la grilla. */
const DIAS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
const FRANJAS = [0, 3, 6, 9, 12, 15, 18, 21]

function indiceDia(d: Date): number {
  return (d.getDay() + 6) % 7
}

// ── Derivaciones ────────────────────────────────────────────────────

interface Tablero {
  total: number
  finalizadas: number
  enCurso: number
  casosDistintos: number
  promedio: number | null
  mejor: number | null
  /** Reparto de sesiones puntuadas por banda, con su fracción del total. */
  distribucion: {
    id: BandaId
    rotulo: string
    color: string
    n: number
    frac: number
  }[]
  /** Promedio por caso, ordenado por cantidad de intentos. */
  porCaso: { titulo: string; intentos: number; promedio: number | null }[]
  /** Últimos 7 días, cada uno con el conteo por banda. */
  semana: { etiqueta: string; porBanda: Record<BandaId, number> }[]
  /** Grilla día × franja de 3 h con el conteo de sesiones. */
  franjas: number[][]
  maxFranja: number
  recientes: SesionHistorial[]
}

function derivar(sesiones: SesionHistorial[]): Tablero {
  const puntuadas = sesiones.filter(
    (s): s is SesionHistorial & { puntaje: number } => s.puntaje !== null,
  )
  const puntajes = puntuadas.map((s) => s.puntaje)

  const conteoBanda = { alto: 0, medio: 0, bajo: 0 } as Record<BandaId, number>
  for (const s of puntuadas) conteoBanda[bandaDe(s.puntaje).id] += 1

  // Un caso puede repetirse: agrupamos por título para promediar los intentos.
  const casos = new Map<string, { intentos: number; suma: number; puntuados: number }>()
  for (const s of sesiones) {
    const clave = s.caso_titulo || s.caso_id || 'Sin caso'
    const acc = casos.get(clave) ?? { intentos: 0, suma: 0, puntuados: 0 }
    acc.intentos += 1
    if (s.puntaje !== null) {
      acc.suma += s.puntaje
      acc.puntuados += 1
    }
    casos.set(clave, acc)
  }

  // Semana móvil: 7 cubetas terminando hoy, para que la última columna sea siempre "hoy".
  const hoy = new Date()
  hoy.setHours(0, 0, 0, 0)
  const semana = Array.from({ length: 7 }, (_, i) => {
    const dia = new Date(hoy)
    dia.setDate(hoy.getDate() - (6 - i))
    return {
      etiqueta: DIAS[indiceDia(dia)],
      porBanda: { alto: 0, medio: 0, bajo: 0 } as Record<BandaId, number>,
    }
  })

  const franjas = Array.from({ length: 7 }, () => Array.from({ length: FRANJAS.length }, () => 0))
  let maxFranja = 0

  for (const s of sesiones) {
    const t = new Date(s.created_at)
    if (Number.isNaN(t.getTime())) continue

    const fila = franjas[indiceDia(t)]
    const col = Math.min(FRANJAS.length - 1, Math.floor(t.getHours() / 3))
    fila[col] += 1
    if (fila[col] > maxFranja) maxFranja = fila[col]

    // Sin puntaje todavía no hay banda: cuenta en la serie recién al cerrarse.
    if (s.puntaje === null) continue
    const dias = Math.floor((t.setHours(0, 0, 0, 0) - hoy.getTime()) / 86_400_000)
    const cubeta = semana[6 + dias]
    if (cubeta) cubeta.porBanda[bandaDe(s.puntaje).id] += 1
  }

  return {
    total: sesiones.length,
    finalizadas: puntuadas.length,
    enCurso: sesiones.filter((s) => s.estado === 'activa').length,
    casosDistintos: casos.size,
    promedio: puntajes.length ? puntajes.reduce((a, b) => a + b, 0) / puntajes.length : null,
    mejor: puntajes.length ? Math.max(...puntajes) : null,
    distribucion: BANDAS.map((b) => ({
      id: b.id,
      rotulo: b.rotulo,
      color: b.color,
      n: conteoBanda[b.id],
      frac: puntuadas.length ? conteoBanda[b.id] / puntuadas.length : 0,
    })),
    porCaso: [...casos.entries()]
      .map(([titulo, a]) => ({
        titulo,
        intentos: a.intentos,
        promedio: a.puntuados ? a.suma / a.puntuados : null,
      }))
      .sort((x, y) => y.intentos - x.intentos),
    semana: semana.map(({ etiqueta, porBanda }) => ({ etiqueta, porBanda })),
    franjas,
    maxFranja,
    recientes: sesiones.slice(0, 6),
  }
}

// ── Piezas de dibujo ────────────────────────────────────────────────

const DONA_R = 52
const DONA_C = 2 * Math.PI * DONA_R

/**
 * Catmull-Rom convertido a Bézier: la curva pasa exactamente por cada punto.
 * Un spline genérico se pasa de largo en los picos y dibuja conteos negativos.
 */
function trazoSuave(puntos: [number, number][]): string {
  if (puntos.length === 0) return ''
  if (puntos.length < 3) {
    return puntos.map(([x, y], i) => `${i ? 'L' : 'M'}${x} ${y}`).join(' ')
  }
  let d = `M${puntos[0][0]} ${puntos[0][1]}`
  for (let i = 0; i < puntos.length - 1; i += 1) {
    const p0 = puntos[i - 1] ?? puntos[i]
    const p1 = puntos[i]
    const p2 = puntos[i + 1]
    const p3 = puntos[i + 2] ?? p2
    d += ` C${p1[0] + (p2[0] - p0[0]) / 6} ${p1[1] + (p2[1] - p0[1]) / 6}`
    d += ` ${p2[0] - (p3[0] - p1[0]) / 6} ${p2[1] - (p3[1] - p1[1]) / 6}`
    d += ` ${p2[0]} ${p2[1]}`
  }
  return d
}

/** Cifra grande con el sufijo en tamaño de marginalia, como en la lámina. */
function Cifra({ valor, sufijo }: { valor: string; sufijo?: string }) {
  return (
    <p className="tablero__cifra">
      {valor}
      {sufijo && <span className="tablero__sufijo">{sufijo}</span>}
    </p>
  )
}

interface PropsTarjeta {
  rotulo: string
  valor: string
  sufijo?: string
  pie: string
  acento: string
}

function Tarjeta({ rotulo, valor, sufijo, pie, acento }: PropsTarjeta) {
  return (
    <article className="tablero__tarjeta" style={{ '--acento': acento } as CSSProperties}>
      <p className="rotulo">{rotulo}</p>
      <Cifra valor={valor} sufijo={sufijo} />
      <p className="tablero__pie">{pie}</p>
    </article>
  )
}

function Panel({
  rotulo,
  titulo,
  extra,
  children,
}: {
  rotulo: string
  titulo: string
  extra?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="tablero__panel">
      <header className="tablero__panel-cab">
        <div>
          <p className="rotulo">{rotulo}</p>
          <h3 className="tablero__panel-titulo">{titulo}</h3>
        </div>
        {extra}
      </header>
      {children}
    </section>
  )
}

/**
 * Lámina: una sección numerada del tablero. Seis paneles sueltos en una grilla
 * se leen como un montón indistinto —el número y la regla dicen dónde empieza
 * cada tema y cuántos temas hay, que es lo que una grilla plana no dice.
 */
function Lamina({
  n,
  titulo,
  nota,
  children,
}: {
  n: string
  titulo: string
  nota?: string
  children: ReactNode
}) {
  return (
    <section className="tablero__lamina">
      <header className="tablero__lamina-cab">
        <span className="tablero__lamina-n">{n}</span>
        <h3 className="tablero__lamina-titulo">{titulo}</h3>
        <span className="tablero__lamina-regla" aria-hidden="true" />
        {nota && <p className="tablero__lamina-nota">{nota}</p>}
      </header>
      {children}
    </section>
  )
}

// ── Componente ──────────────────────────────────────────────────────

export function MetricasUso() {
  const [estado, setEstado] = useState<Estado>('cargando')
  const [sesiones, setSesiones] = useState<SesionHistorial[]>([])
  const [error, setError] = useState<string | null>(null)

  // Bloque `demo`: pinta el tablero con datos sintéticos cuando no hay reales
  // (o siempre, con `?demo`). Ver src/lib/demo.ts para borrarlo.
  const preferencia = preferenciaDemo()
  const [demo, setDemo] = useState(preferencia === 'forzado')

  useEffect(() => {
    if (preferencia === 'forzado') {
      setSesiones(sesionesDemo())
      setDemo(true)
      setEstado('listo')
      return
    }
    let vigente = true
    api
      .obtenerHistorial()
      .then((datos) => {
        if (!vigente) return
        // Historial vacío: el tablero completo con datos de ejemplo dice mucho
        // más que seis paneles en blanco. Se retira solo al primer caso real.
        const relleno = datos.length === 0 && preferencia === 'auto'
        setSesiones(relleno ? sesionesDemo() : datos)
        setDemo(relleno)
        setEstado('listo')
      })
      .catch((err) => {
        if (!vigente) return
        setError(err instanceof Error ? err.message : 'No se pudieron calcular las métricas.')
        setEstado('error')
      })
    return () => {
      vigente = false
    }
  }, [preferencia])

  const t = useMemo(() => derivar(sesiones), [sesiones])

  if (estado === 'error') {
    return (
      <section className="tablero">
        <div className="alerta" role="alert">
          <span>{error}</span>
        </div>
      </section>
    )
  }

  if (estado === 'cargando') {
    return (
      <section className="tablero">
        <Lamina n="01" titulo="Resumen">
          <div className="tablero__kpis">
            {[0, 1, 2, 3].map((i) => (
              <div
                key={i}
                className="tablero__tarjeta tablero__tarjeta--skeleton"
                aria-hidden="true"
              />
            ))}
          </div>
        </Lamina>
        <Lamina n="02" titulo="Desempeño">
          <div className="tablero__grid tablero__grid--duo">
            <div className="tablero__panel tablero__panel--skeleton" aria-hidden="true" />
            <div className="tablero__panel tablero__panel--skeleton" aria-hidden="true" />
          </div>
        </Lamina>
      </section>
    )
  }

  if (t.total === 0) {
    return (
      <section className="tablero">
        <Cabecera total={0} demo={demo} />
        <div className="tablero__panel tablero__vacio">
          <p>Todavía no hay sesiones registradas.</p>
          <p className="tablero__pie">
            Completá un caso y el tablero se arma solo con tus propios datos.
          </p>
        </div>
      </section>
    )
  }

  const maxSemana = Math.max(
    1,
    ...t.semana.map((d) => Math.max(...BANDAS.map((b) => d.porBanda[b.id]))),
  )

  return (
    <section className="tablero">
      <Cabecera total={t.total} demo={demo} />

      <Lamina n="01" titulo="Resumen" nota="Totales acumulados">
        <div className="tablero__kpis">
          <Tarjeta
            rotulo="Sesiones totales"
            valor={String(t.total)}
            pie={`${t.casosDistintos} caso${t.casosDistintos === 1 ? '' : 's'} distinto${t.casosDistintos === 1 ? '' : 's'}`}
            acento="var(--tinta)"
          />
          <Tarjeta
            rotulo="Casos evaluados"
            valor={String(t.finalizadas)}
            pie={t.enCurso > 0 ? `${t.enCurso} todavía en curso` : 'Ninguna sesión abierta'}
            acento="var(--oxido)"
          />
          <Tarjeta
            rotulo="Puntaje promedio"
            valor={t.promedio !== null ? t.promedio.toFixed(1) : '—'}
            sufijo={t.promedio !== null ? '/100' : undefined}
            pie="Sobre las sesiones cerradas"
            acento="var(--ambar)"
          />
          <Tarjeta
            rotulo="Mejor puntaje"
            valor={t.mejor !== null ? String(t.mejor) : '—'}
            sufijo={t.mejor !== null ? '/100' : undefined}
            pie="Tope histórico"
            acento="var(--verde)"
          />
        </div>
      </Lamina>

      <Lamina n="02" titulo="Desempeño" nota="Sobre sesiones cerradas">
        <div className="tablero__grid tablero__grid--duo">
          {/* Distribución por banda */}
          <Panel rotulo="Distribución" titulo="Sesiones evaluadas">
            {t.finalizadas === 0 ? (
              <p className="tablero__pie">Sin sesiones cerradas todavía.</p>
            ) : (
              <div className="tablero__dona-fila">
                <svg
                  className="tablero__dona"
                  viewBox="0 0 140 140"
                  role="img"
                  aria-label="Distribución por banda de desempeño"
                >
                  <circle cx="70" cy="70" r={DONA_R} className="tablero__dona-riel" />
                  {(() => {
                    let acc = 0
                    return t.distribucion
                      .filter((d) => d.frac > 0)
                      .map((d) => {
                        const offset = -acc * DONA_C
                        acc += d.frac
                        return (
                          <circle
                            key={d.id}
                            cx="70"
                            cy="70"
                            r={DONA_R}
                            className="tablero__dona-arco"
                            stroke={d.color}
                            strokeDasharray={`${d.frac * DONA_C} ${DONA_C}`}
                            strokeDashoffset={offset}
                          />
                        )
                      })
                  })()}
                </svg>

                <dl className="tablero__leyenda">
                  {t.distribucion.map((d) => (
                    <div key={d.id}>
                      <dt>
                        <span className="tablero__punto" style={{ background: d.color }} />
                        {d.rotulo}
                      </dt>
                      <dd>
                        <span
                          className="tablero__cifra tablero__cifra--chica"
                          style={{ color: d.color }}
                        >
                          {Math.round(d.frac * 100)}
                          <span className="tablero__sufijo">%</span>
                        </span>
                        <span className="tablero__pie">
                          {d.n} sesi{d.n === 1 ? 'ón' : 'ones'}
                        </span>
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}
          </Panel>

          {/* Promedio por caso */}
          <Panel rotulo="Rendimiento por caso" titulo="Promedio alcanzado">
            <ul className="tablero__barras">
              {t.porCaso.slice(0, 4).map((c) => {
                const color = c.promedio !== null ? bandaDe(c.promedio).color : 'var(--tinta-tenue)'
                return (
                  <li key={c.titulo} className="tablero__barra">
                    <div className="tablero__barra-cab">
                      <span className="rotulo tablero__barra-rotulo">{c.titulo}</span>
                      <span className="tablero__cifra tablero__cifra--chica" style={{ color }}>
                        {c.promedio !== null ? c.promedio.toFixed(0) : '—'}
                        {c.promedio !== null && <span className="tablero__sufijo">/100</span>}
                      </span>
                    </div>
                    <div className="tablero__riel">
                      <span
                        className="tablero__relleno"
                        style={{
                          width: `${c.promedio ?? 0}%`,
                          background: color,
                        }}
                      />
                    </div>
                    <p className="tablero__pie">
                      {c.intentos} intento{c.intentos === 1 ? '' : 's'}
                      {c.promedio === null && ' · sin evaluar'}
                    </p>
                  </li>
                )
              })}
            </ul>
          </Panel>
        </div>
      </Lamina>

      <Lamina n="03" titulo="Ritmo de práctica" nota="Cuándo y cuánto">
        <div className="tablero__grid tablero__grid--ritmo">
          {/* Serie semanal */}
          <Panel
            rotulo="Últimos 7 días"
            titulo="Sesiones por día"
            extra={
              <ul className="tablero__leyenda-inline">
                {BANDAS.map((b) => (
                  <li key={b.id}>
                    <span className="tablero__punto" style={{ background: b.color }} />
                    <span className="rotulo">{b.rotulo}</span>
                  </li>
                ))}
              </ul>
            }
          >
            <svg
              className="tablero__serie"
              viewBox="0 0 620 220"
              role="img"
              aria-label="Sesiones por día de la última semana"
            >
              {[0, 0.25, 0.5, 0.75, 1].map((f) => (
                <line
                  key={f}
                  x1="0"
                  x2="620"
                  y1={20 + f * 160}
                  y2={20 + f * 160}
                  className="tablero__reja"
                />
              ))}
              {BANDAS.map((b) => {
                const puntos = t.semana.map(
                  (d, i) =>
                    [(i / 6) * 600 + 10, 180 - (d.porBanda[b.id] / maxSemana) * 160] as [
                      number,
                      number,
                    ],
                )
                return (
                  <path
                    key={b.id}
                    d={trazoSuave(puntos)}
                    fill="none"
                    stroke={b.color}
                    strokeWidth="2"
                  />
                )
              })}
            </svg>
            <ol className="tablero__eje">
              {t.semana.map((d, i) => (
                <li key={i} className="rotulo">
                  {d.etiqueta}
                </li>
              ))}
            </ol>
          </Panel>

          {/* Mapa de calor */}
          <Panel rotulo="Franja horaria" titulo="Horas de práctica">
            <div className="tablero__calor">
              <ol className="tablero__calor-horas">
                {FRANJAS.map((h) => (
                  <li key={h} className="rotulo">
                    {String(h).padStart(2, '0')}
                  </li>
                ))}
              </ol>
              {t.franjas.map((fila, d) => (
                <div key={d} className="tablero__calor-fila">
                  <span className="rotulo tablero__calor-dia">{DIAS[d].slice(0, 1)}</span>
                  {fila.map((n, f) => (
                    <span
                      key={f}
                      className="tablero__celda"
                      style={{
                        // Piso de 0.1: sobre papel, un ámbar más transparente
                        // que eso desaparece y la grilla queda con agujeros en
                        // lugar de con celdas vacías.
                        opacity: n === 0 ? 0.1 : 0.28 + (n / t.maxFranja) * 0.72,
                      }}
                      title={`${DIAS[d]} ${String(FRANJAS[f]).padStart(2, '0')}:00 — ${n} sesión(es)`}
                    />
                  ))}
                </div>
              ))}
              <p className="tablero__calor-escala rotulo">
                Menos
                {[0.1, 0.32, 0.54, 0.77, 1].map((o) => (
                  <span key={o} className="tablero__celda" style={{ opacity: o }} />
                ))}
                Más
              </p>
            </div>
          </Panel>
        </div>
      </Lamina>

      <Lamina n="04" titulo="Registro" nota="Volumen por caso y últimos movimientos">
        <div className="tablero__grid tablero__grid--duo">
          {/* Casos más practicados */}
          <Panel rotulo="Volumen por caso" titulo="Más practicados">
            <ul className="tablero__ranking">
              {t.porCaso.slice(0, 6).map((c) => (
                <li key={c.titulo}>
                  <span className="tablero__ranking-rotulo">{c.titulo}</span>
                  <span
                    className="tablero__ranking-barra"
                    style={{
                      width: `${(c.intentos / t.porCaso[0].intentos) * 100}%`,
                    }}
                  />
                  <span className="tablero__ranking-n">{c.intentos}</span>
                </li>
              ))}
            </ul>
          </Panel>

          {/* Últimas sesiones */}
          <Panel rotulo="Actividad reciente" titulo="Últimas sesiones">
            <ul className="tablero__recientes">
              {t.recientes.map((s) => {
                const banda = s.puntaje !== null ? bandaDe(s.puntaje) : null
                return (
                  <li key={s.sesion_id}>
                    <span
                      className="tablero__id"
                      style={{ color: banda?.color ?? 'var(--tinta-tenue)' }}
                    >
                      {s.sesion_id.slice(0, 8)}
                    </span>
                    <p className="tablero__reciente-caso">{s.caso_titulo}</p>
                    <p className="tablero__reciente-meta">
                      <span
                        className="tablero__punto"
                        style={{
                          background: banda?.color ?? 'var(--tinta-tenue)',
                        }}
                      />
                      <span
                        className="rotulo"
                        style={{ color: banda?.color ?? 'var(--tinta-tenue)' }}
                      >
                        {banda ? banda.rotulo : 'En curso'}
                      </span>
                      {s.puntaje !== null && <span className="tablero__pie">{s.puntaje}/100</span>}
                    </p>
                  </li>
                )
              })}
            </ul>
          </Panel>
        </div>
      </Lamina>
    </section>
  )
}

function Cabecera({ total, demo }: { total: number; demo: boolean }) {
  return (
    <>
      {demo && (
        <p className="tablero__demo rotulo">
          Datos de demostración — generados en el navegador, no son tus sesiones. Se reemplazan por
          las reales apenas completes un caso; <code>?demo=0</code> los apaga.
        </p>
      )}
      <header className="tablero__cabecera">
        <div>
          <p className="rotulo">/ Métricas de uso</p>
          <h2 className="tablero__titulo">Tu actividad</h2>
          <p className="tablero__bajada">
            {demo
              ? 'Vista previa del tablero con datos sintéticos.'
              : 'Calculado sobre tus sesiones registradas. Sin datos de ejemplo.'}
          </p>
        </div>
        <p
          className="tablero__sello rotulo"
          style={
            demo
              ? {
                  borderColor: 'rgb(166 112 42 / 0.5)',
                  color: 'var(--ambar)',
                }
              : undefined
          }
        >
          <span
            className="tablero__punto"
            style={{
              background: demo ? 'var(--ambar)' : 'var(--verde)',
            }}
          />
          {demo ? 'Demo · ' : ''}
          {total} registro{total === 1 ? '' : 's'}
        </p>
      </header>
    </>
  )
}
