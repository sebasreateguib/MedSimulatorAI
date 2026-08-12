import type { EvaluacionClinica, SesionHistorial } from '../types'

/**
 * Datos sintéticos para mirar el tablero y el historial con todos sus paneles
 * cargados sin tener que jugar cincuenta casos a mano.
 *
 * Se activa SOLO con `?demo` en la URL y ambas vistas lo anuncian con una banda
 * bien visible: no hay forma de que estos números se confundan con los reales
 * ni de que se cuelen en una sesión normal.
 *
 * Para borrarlo: eliminar este archivo y los bloques `demo` en MetricasUso.tsx
 * y HistorialSesiones.tsx.
 */

/** Cada caso viaja con su paciente: el historial muestra ambos en la fila. */
const CASOS_DEMO = [
  { titulo: 'Fibrilación Auricular Aguda', paciente: 'Ramón Ovalle, 68' },
  { titulo: 'Síndrome Coronario Agudo', paciente: 'Delia Marchetti, 57' },
  { titulo: 'Cetoacidosis Diabética', paciente: 'Iván Quiroga, 24' },
  { titulo: 'Neumonía Adquirida en Comunidad', paciente: 'Sofía Belaúnde, 71' },
  { titulo: 'Accidente Cerebrovascular', paciente: 'Héctor Nualart, 63' },
  { titulo: 'Abdomen Agudo Quirúrgico', paciente: 'Camila Ferreyra, 33' },
]

/**
 * PRNG con semilla fija (mulberry32): el tablero se ve idéntico en cada
 * recarga. Con `Math.random()` los gráficos bailan entre refrescos y no se
 * puede juzgar un ajuste de diseño.
 */
function prng(semilla: number): () => number {
  let a = semilla
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function sesionesDemo(): SesionHistorial[] {
  const rnd = prng(20260812)
  const sesiones: SesionHistorial[] = []
  const ahora = new Date()

  // 10 días hacia atrás: la serie semanal se llena y el mapa de calor junta
  // suficientes repeticiones como para mostrar gradiente y no solo binario.
  for (let dia = 9; dia >= 0; dia -= 1) {
    const fecha = new Date(ahora)
    fecha.setDate(ahora.getDate() - dia)
    const finDeSemana = fecha.getDay() === 0 || fecha.getDay() === 6

    // Se estudia de noche y poco el fin de semana: le da forma al mapa de calor.
    const cantidad = finDeSemana ? Math.floor(rnd() * 3) : 2 + Math.floor(rnd() * 6)

    for (let i = 0; i < cantidad; i += 1) {
      const hora = rnd() < 0.65 ? 18 + Math.floor(rnd() * 5) : 8 + Math.floor(rnd() * 8)
      const t = new Date(fecha)
      t.setHours(hora, Math.floor(rnd() * 60), 0, 0)

      // El caso 0 es el que más se practica: da un ranking con pendiente real.
      const idxCaso = rnd() < 0.3 ? 0 : Math.floor(rnd() * CASOS_DEMO.length)

      // Curva de aprendizaje: los puntajes suben a medida que se acerca a hoy.
      const progreso = (9 - dia) / 9
      const base = 48 + progreso * 30
      const puntaje = Math.max(12, Math.min(99, Math.round(base + (rnd() - 0.45) * 34)))

      // Las últimas horas dejan alguna sesión abierta, como en el uso real.
      const activa = dia === 0 && rnd() < 0.35

      sesiones.push({
        sesion_id: Math.floor(rnd() * 0xffffffff).toString(16).padStart(8, '0') + '-demo',
        caso_id: `demo_${idxCaso}`,
        caso_titulo: CASOS_DEMO[idxCaso].titulo,
        paciente_nombre: CASOS_DEMO[idxCaso].paciente,
        estado: activa ? 'activa' : 'finalizada',
        puntaje: activa ? null : puntaje,
        created_at: t.toISOString(),
      })
    }
  }

  // El historial real llega con el más reciente primero.
  return sesiones.reverse()
}

/**
 * Scorecard sintético para una sesión del historial demo. Sin esto, tocar un
 * puntaje llamaría a `/evaluacion/<id>` con un id que no existe y la vista
 * mostraría un error en medio de la demostración.
 *
 * El texto se elige por banda de puntaje: un 91 y un 38 no pueden leer igual.
 */
export function evaluacionDemo(sesion: SesionHistorial): EvaluacionClinica {
  const puntaje = sesion.puntaje ?? 0
  const caso = sesion.caso_titulo

  if (puntaje >= 80) {
    return {
      puntaje_total: puntaje,
      razonamiento_diagnostico: `Anamnesis dirigida y ordenada. Llegaste a ${caso.toLowerCase()} con las preguntas justas y descartaste los diferenciales en el orden correcto.`,
      costo_efectividad:
        'Estudios bien elegidos: cada pedido cambiaba la conducta. Buen uso de los recursos disponibles.',
      pruebas_innecesarias: [],
      errores_criticos: [],
      retroalimentacion:
        'Desempeño sólido. El siguiente paso es acortar el tiempo hasta la primera conducta terapéutica sin perder la sistemática que ya tenés.',
    }
  }

  if (puntaje >= 60) {
    return {
      puntaje_total: puntaje,
      razonamiento_diagnostico: `Identificaste ${caso.toLowerCase()}, pero llegaste tarde: faltó explorar antecedentes y factores de riesgo antes de pedir estudios.`,
      costo_efectividad:
        'Algunos estudios se pidieron en paralelo cuando convenía escalonarlos según el resultado del anterior.',
      pruebas_innecesarias: ['Panel metabólico completo en la primera tanda'],
      errores_criticos: [],
      retroalimentacion:
        'Vas bien encaminado. Trabajá la hipótesis diagnóstica antes de pedir: definí qué esperás que cambie con cada estudio.',
    }
  }

  return {
    puntaje_total: puntaje,
    razonamiento_diagnostico: `No se llegó al diagnóstico de ${caso.toLowerCase()}. La anamnesis quedó incompleta y se saltearon signos de alarma presentes desde el inicio.`,
    costo_efectividad:
      'Se pidieron estudios de alto costo sin una hipótesis que los justifique.',
    pruebas_innecesarias: ['Tomografía de tórax', 'Panel de autoinmunidad'],
    errores_criticos: [
      'No se tomaron signos vitales antes de indicar tratamiento',
      'No se reevaluó al paciente tras la primera intervención',
    ],
    retroalimentacion:
      'Repasá la sistemática inicial: signos vitales, motivo de consulta y antecedentes antes de cualquier estudio. Volvé a intentar este caso.',
  }
}

/**
 * Preferencia de demo tomada de la URL:
 *
 * - `forzado`  → `?demo` (o `?demo=1`): datos sintéticos aunque haya reales.
 * - `apagado`  → `?demo=0` / `?demo=off`: nunca sintéticos, ni con historial vacío.
 * - `auto`     → sin parámetro: reales si los hay, sintéticos si el historial
 *                está vacío. Es el default para que el tablero no se vea muerto
 *                en una cuenta recién creada.
 *
 * El parámetro va en el query string, antes del `#`: `/?demo#simulador`.
 */
export type PreferenciaDemo = 'forzado' | 'apagado' | 'auto'

const APAGADO = new Set(['0', 'off', 'false', 'no'])

export function preferenciaDemo(): PreferenciaDemo {
  const params = new URLSearchParams(window.location.search)
  if (!params.has('demo')) return 'auto'
  return APAGADO.has((params.get('demo') ?? '').toLowerCase()) ? 'apagado' : 'forzado'
}
