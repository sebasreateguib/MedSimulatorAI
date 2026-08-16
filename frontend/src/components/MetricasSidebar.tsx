import { useEffect, useMemo, useState } from 'react'
import { derivar } from './Metricas'
import * as api from '../lib/api'
import { preferenciaDemo, sesionesDemo } from '../lib/demo'
import type { SesionHistorial } from '../types'

/** Días del pulso de constancia. 14 entran cómodos en el ancho del sidebar. */
const DIAS_PULSO = 14

interface Props {
  /**
   * Cambiar este número vuelve a pedir los datos. La sesión que recién termina
   * o el documento que se acaba de subir tienen que verse acá sin recargar.
   */
  version: number
}

/**
 * Resumen compacto al pie del sidebar: los cuatro números que contestan "¿cómo
 * vengo?" sin abrir el tablero.
 *
 * Los cálculos salen de `derivar()`, el mismo del tablero de métricas, para que
 * la racha que muestra acá y la que muestra allá no puedan discrepar.
 */
export function MetricasSidebar({ version }: Props) {
  const [sesiones, setSesiones] = useState<SesionHistorial[] | null>(null)
  const [documentos, setDocumentos] = useState<number | null>(null)

  // Mismo criterio que el tablero: con `?demo` los números son sintéticos y el
  // bloque lo dice. Ver src/lib/demo.ts.
  const preferencia = preferenciaDemo()
  const demo = preferencia === 'forzado'

  useEffect(() => {
    if (demo) {
      setSesiones(sesionesDemo())
      setDocumentos(4)
      return
    }

    let vigente = true
    // Los dos pedidos van juntos y cada uno resuelve por su lado: que falle el
    // conteo de material no puede dejar el bloque entero sin números.
    api.obtenerHistorial().then(
      (datos) => vigente && setSesiones(datos),
      () => vigente && setSesiones([]),
    )
    api.resumenBiblioteca().then(
      (r) => vigente && setDocumentos(r.documentos),
      () => vigente && setDocumentos(null),
    )
    return () => {
      vigente = false
    }
  }, [demo, version])

  const t = useMemo(() => derivar(sesiones ?? []), [sesiones])

  // Nada que resumir todavía: en vez de una fila de ceros —que se lee como un
  // error— va la invitación a empezar.
  if (sesiones !== null && sesiones.length === 0) {
    return (
      <div className="resumen resumen--vacio group-data-[collapsible=icon]:hidden">
        <p className="resumen__titulo">Resumen</p>
        <p className="resumen__nota">
          Todavía no simulaste ningún caso. Los números aparecen con el primero.
        </p>
      </div>
    )
  }

  // Mientras no llegó el historial, todo va con guiones: un "0 días" de racha
  // que aparece medio segundo y salta a 8 se lee como un error de cálculo.
  const cargando = sesiones === null
  const pulso = t.tira.slice(-DIAS_PULSO)

  return (
    <div className="resumen group-data-[collapsible=icon]:hidden" aria-live="polite">
      <p className="resumen__titulo">
        Resumen
        {demo && <span className="resumen__demo">ejemplo</span>}
      </p>

      <dl className="resumen__grilla">
        <Cifra rotulo="Casos" valor={cargando ? '—' : String(t.total)} />
        <Cifra
          rotulo="Promedio"
          valor={!cargando && t.promedio !== null ? t.promedio.toFixed(0) : '—'}
          sufijo={!cargando && t.promedio !== null ? '/100' : undefined}
          acento={!cargando && t.promedio !== null && t.promedio >= 80}
        />
        <Cifra
          rotulo="Racha"
          valor={cargando ? '—' : String(t.rachaActual)}
          sufijo={cargando ? undefined : t.rachaActual === 1 ? 'día' : 'días'}
        />
        <Cifra
          rotulo="Material"
          valor={documentos === null ? '—' : String(documentos)}
          sufijo={documentos === null ? undefined : 'doc'}
        />
      </dl>

      {/* Un casillero por día: encendido si hubo al menos una sesión. Es el
          mismo pulso del tablero, recortado a las dos últimas semanas. */}
      <div
        className="resumen__pulso"
        title={`${t.diasActivos} días activos en los últimos 30`}
        aria-label={`${t.diasActivos} días activos en los últimos 30`}
      >
        {pulso.map((dia, i) => (
          <span
            key={i}
            className={`resumen__dia${dia.n > 0 ? ' resumen__dia--activo' : ''}`}
          />
        ))}
      </div>
    </div>
  )
}

interface PropsCifra {
  rotulo: string
  valor: string
  sufijo?: string
  acento?: boolean
}

function Cifra({ rotulo, valor, sufijo, acento }: PropsCifra) {
  return (
    <div className="resumen__celda">
      <dt>{rotulo}</dt>
      <dd className={acento ? 'resumen__valor resumen__valor--alto' : 'resumen__valor'}>
        {valor}
        {sufijo && <span className="resumen__sufijo">{sufijo}</span>}
      </dd>
    </div>
  )
}
