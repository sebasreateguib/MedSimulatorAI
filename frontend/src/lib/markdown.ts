/**
 * Analizador de Markdown a medida, sin dependencias.
 *
 * Por qué no `react-markdown`: la respuesta del tutor llega token a token y trae
 * marcas de cita `[n]` que tienen que salir como botones dentro del párrafo. Con
 * una librería habría que reparsear el documento entero en cada token y volver a
 * pinchar sus nodos de texto para inyectar las citas. Acá el parseo es lineal y
 * las citas son un tipo de trozo más.
 *
 * Es deliberadamente incompleto: cubre lo que un modelo escribe cuando se le
 * pide que ordene una respuesta —encabezados, listas, tablas, negritas, código—
 * y nada más. No hay anidamiento arbitrario ni HTML embebido.
 *
 * Todo lo que no reconoce sale como texto plano, que es lo que corresponde
 * mientras el markdown está a medio escribir: un `**` sin cerrar se lee como
 * dos asteriscos y no se come el resto del mensaje.
 */

export type Bloque =
  | { tipo: 'parrafo'; texto: string }
  | { tipo: 'encabezado'; nivel: 1 | 2 | 3; texto: string }
  | { tipo: 'lista'; ordenada: boolean; items: ItemLista[] }
  | { tipo: 'cita'; lineas: string[] }
  | { tipo: 'codigo'; lenguaje: string | null; texto: string }
  | { tipo: 'tabla'; encabezados: string[]; filas: string[][] }
  | { tipo: 'regla' }

export interface ItemLista {
  texto: string
  /** 0 = primer nivel, 1 = sangrado. No se soporta más profundidad. */
  nivel: number
}

const ENCABEZADO = /^(#{1,6})\s+(.*)$/
const VINETA = /^(\s*)[-*+]\s+(.*)$/
const NUMERADA = /^(\s*)\d+[.)]\s+(.*)$/
const REGLA = /^\s*([-*_])\s*(\1\s*){2,}$/
const CERCA = /^\s*```(.*)$/
const CITA = /^\s*>\s?(.*)$/
const FILA_TABLA = /^\s*\|(.+)\|\s*$/
const SEPARADOR_TABLA = /^\s*\|?[\s:|-]+\|[\s:|-]*$/

/** Parte el markdown en bloques. Nunca lanza: lo desconocido cae a párrafo. */
export function analizarBloques(markdown: string): Bloque[] {
  const lineas = markdown.replace(/\r\n/g, '\n').split('\n')
  const bloques: Bloque[] = []
  let i = 0

  while (i < lineas.length) {
    const linea = lineas[i]

    if (!linea.trim()) {
      i += 1
      continue
    }

    // Código cercado. Si el cierre nunca llega —respuesta a medio escribir—
    // se toma hasta el final: mejor un bloque de código abierto que ver los
    // backticks sueltos y el contenido desarmado.
    const cerca = CERCA.exec(linea)
    if (cerca) {
      const lenguaje = cerca[1].trim() || null
      const cuerpo: string[] = []
      i += 1
      while (i < lineas.length && !CERCA.test(lineas[i])) {
        cuerpo.push(lineas[i])
        i += 1
      }
      i += 1 // consume el cierre (o pasa del final, que es inofensivo)
      bloques.push({ tipo: 'codigo', lenguaje, texto: cuerpo.join('\n') })
      continue
    }

    if (REGLA.test(linea)) {
      bloques.push({ tipo: 'regla' })
      i += 1
      continue
    }

    const encabezado = ENCABEZADO.exec(linea)
    if (encabezado) {
      // Más de tres niveles no aportan jerarquía visible en una burbuja de chat.
      const nivel = Math.min(encabezado[1].length, 3) as 1 | 2 | 3
      bloques.push({ tipo: 'encabezado', nivel, texto: encabezado[2].trim() })
      i += 1
      continue
    }

    // Tabla: fila de encabezados seguida de la de guiones. Sin esa segunda
    // línea es texto con pipes, no una tabla.
    if (FILA_TABLA.test(linea) && i + 1 < lineas.length && SEPARADOR_TABLA.test(lineas[i + 1])) {
      const encabezados = celdas(linea)
      const filas: string[][] = []
      i += 2
      while (i < lineas.length && FILA_TABLA.test(lineas[i])) {
        filas.push(celdas(lineas[i]))
        i += 1
      }
      bloques.push({ tipo: 'tabla', encabezados, filas })
      continue
    }

    if (CITA.test(linea)) {
      const cuerpo: string[] = []
      while (i < lineas.length && CITA.test(lineas[i])) {
        cuerpo.push((CITA.exec(lineas[i]) as RegExpExecArray)[1])
        i += 1
      }
      bloques.push({ tipo: 'cita', lineas: cuerpo })
      continue
    }

    if (VINETA.test(linea) || NUMERADA.test(linea)) {
      const ordenada = NUMERADA.test(linea) && !VINETA.test(linea)
      const items: ItemLista[] = []

      while (i < lineas.length) {
        const item = VINETA.exec(lineas[i]) ?? NUMERADA.exec(lineas[i])
        if (item) {
          items.push({ texto: item[2], nivel: item[1].length >= 2 ? 1 : 0 })
          i += 1
          continue
        }
        // Una línea suelta y sangrada continúa el item anterior en vez de
        // abrir un párrafo huérfano en medio de la lista.
        if (items.length > 0 && /^\s+\S/.test(lineas[i])) {
          items[items.length - 1].texto += ` ${lineas[i].trim()}`
          i += 1
          continue
        }
        break
      }

      bloques.push({ tipo: 'lista', ordenada, items })
      continue
    }

    // Párrafo: hasta la línea en blanco o hasta que empiece otro bloque.
    const parrafo: string[] = []
    while (i < lineas.length && lineas[i].trim() && !empiezaBloque(lineas[i])) {
      parrafo.push(lineas[i].trim())
      i += 1
    }
    if (parrafo.length > 0) {
      bloques.push({ tipo: 'parrafo', texto: parrafo.join(' ') })
    } else {
      // Salvaguarda: si la línea abría un bloque, ya se habría consumido arriba.
      // Sin este avance, un caso no previsto colgaría el bucle.
      bloques.push({ tipo: 'parrafo', texto: lineas[i].trim() })
      i += 1
    }
  }

  return bloques
}

function empiezaBloque(linea: string): boolean {
  return (
    ENCABEZADO.test(linea) ||
    VINETA.test(linea) ||
    NUMERADA.test(linea) ||
    REGLA.test(linea) ||
    CERCA.test(linea) ||
    CITA.test(linea) ||
    FILA_TABLA.test(linea)
  )
}

function celdas(linea: string): string[] {
  return linea
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((c) => c.trim())
}

// ── Inline ──────────────────────────────────────────────────────────

export type Trozo =
  | { tipo: 'texto'; texto: string }
  | { tipo: 'fuerte'; texto: string }
  | { tipo: 'enfasis'; texto: string }
  | { tipo: 'codigo'; texto: string }
  | { tipo: 'enlace'; texto: string; url: string }
  | { tipo: 'cita'; n: number }

/**
 * Un solo barrido con alternancia: código primero (adentro no se interpreta
 * nada), después enlaces, negrita, énfasis y por último las marcas de cita.
 *
 * El orden importa: `[3]` es una cita, pero `[ver acá](url)` es un enlace, así
 * que la alternativa del enlace tiene que ir antes que la de la cita.
 */
/**
 * Marca de cita, simple o agrupada: los modelos escriben tanto `[1]` como
 * `[1, 2]` cuando una afirmación se apoya en varios fragmentos.
 *
 * Se define una sola vez porque la usan el analizador y `pareceMarkdown`: con
 * una copia en cada lado, un texto cuya única marca era `[1, 2]` se detectaba
 * como texto plano y salía sin citas clickeables.
 */
const CITA_INLINE = '\\[(\\d{1,3}(?:\\s*,\\s*\\d{1,3})*)\\]'

const INLINE = new RegExp(
  [
    '`([^`]+)`', // 1: código
    '\\*\\*([^*]+)\\*\\*', // 2: negrita
    '__([^_]+)__', // 3: negrita
    '\\[([^\\]]+)\\]\\(([^)\\s]+)\\)', // 4,5: enlace
    CITA_INLINE, // 6: cita
    '\\*([^*\\n]+)\\*', // 7: énfasis
    '(?<![A-Za-z0-9])_([^_\\n]+)_(?![A-Za-z0-9])', // 8: énfasis
  ].join('|'),
  'g',
)

export function analizarInline(texto: string): Trozo[] {
  const trozos: Trozo[] = []
  let cursor = 0

  INLINE.lastIndex = 0
  let m: RegExpExecArray | null
  while ((m = INLINE.exec(texto)) !== null) {
    if (m.index > cursor) {
      trozos.push({ tipo: 'texto', texto: texto.slice(cursor, m.index) })
    }

    if (m[1] !== undefined) trozos.push({ tipo: 'codigo', texto: m[1] })
    else if (m[2] !== undefined) trozos.push({ tipo: 'fuerte', texto: m[2] })
    else if (m[3] !== undefined) trozos.push({ tipo: 'fuerte', texto: m[3] })
    else if (m[4] !== undefined) trozos.push({ tipo: 'enlace', texto: m[4], url: m[5] })
    else if (m[6] !== undefined) {
      // Un grupo se abre en una marca por fuente: cada número lleva a su propio
      // fragmento, y una sola marca "[1, 2]" no podría llevar a los dos.
      for (const numero of m[6].split(',')) {
        trozos.push({ tipo: 'cita', n: Number(numero.trim()) })
      }
    }
    else if (m[7] !== undefined) trozos.push({ tipo: 'enfasis', texto: m[7] })
    else if (m[8] !== undefined) trozos.push({ tipo: 'enfasis', texto: m[8] })

    cursor = m.index + m[0].length
  }

  if (cursor < texto.length) {
    trozos.push({ tipo: 'texto', texto: texto.slice(cursor) })
  }
  return trozos
}

/**
 * ¿Vale la pena pasar este texto por el renderizador?
 *
 * La respuesta del paciente virtual es habla, no documento: envolverla en
 * párrafos y buscarle listas no aporta nada. Solo se formatea lo que trae
 * alguna marca real de markdown.
 */
const MARCAS = new RegExp(
  [
    '(^|\\n)\\s*(#{1,6}\\s|[-*+]\\s|\\d+[.)]\\s|>\\s|```|\\|)', // bloques
    '\\*\\*|__|`[^`]+`', // énfasis y código inline
    CITA_INLINE, // citas
  ].join('|'),
)

export function pareceMarkdown(texto: string): boolean {
  return MARCAS.test(texto)
}
