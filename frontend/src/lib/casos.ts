import type { Caso } from '../types'

/**
 * Espejo mínimo de config/casos/*.yaml para poder elegir caso mientras el
 * backend no expone el catálogo. Solo datos que el estudiante puede ver antes
 * de empezar: nada de historia oculta ni diagnóstico.
 */
export const CASOS_LOCALES: Caso[] = [
  {
    id: 'fa_aguda_001',
    titulo: 'Fibrilación Auricular Aguda',
    motivo_consulta: 'Palpitaciones rápidas e irregulares con sensación de angustia.',
    paciente: { nombre: 'Carlos Mendoza', edad: 68, genero: 'Masculino' },
    dificultad: 'intermedio',
  },
]
