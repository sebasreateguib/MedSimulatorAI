interface Props {
  /** Lado en px. El trazo es geométrico, así que escala sin perder filo. */
  size?: number
  className?: string
  /** Si se pasa, la marca es contenido: se anuncia con este texto. Si no, es decorativa. */
  titulo?: string
}

/**
 * Marca de MedSimulator AI — la M sobre la lámina.
 *
 * Monograma monolineal en hueso sobre lámina de tinta, con un lomo de óxido en
 * el canto izquierdo. Tres elementos y nada más: la lámina, la letra, el lomo.
 *
 * Decisiones de dibujo:
 *
 * - El lomo no es decoración: sobre fondos oscuros —la cabecera flotando en el
 *   hero, el sidebar, la lámina de acceso— la placa de tinta se funde con el
 *   fondo y la marca se queda sin caja. El filete la recorta y el lomo le
 *   devuelve el color de la casa. También es la referencia de siempre: el canto
 *   teñido de un volumen encuadernado.
 * - El acento vive en la lámina, nunca dentro de la letra. Probado al revés
 *   —el valle de la M en óxido— la punta lee como un corazón.
 * - Valle profundo (22.3 sobre una caja que baja a 25.1): con la V a media
 *   altura la M queda genérica; bajarla casi hasta la base es lo que le da
 *   carácter sin agregar un solo elemento.
 * - `stroke-miterlimit="3"` bisela los dos vértices de arriba y deja filoso el
 *   del medio. Las puntas superiores caen en 4.35 y sin declararlo quedaban
 *   justo en el umbral por defecto: el mismo dibujo salía con punta o sin ella
 *   según el motor. El corte plano es la decisión, y así queda escrita.
 * - La letra va 0.5 arriba del centro geométrico. Centrada de verdad, se ve
 *   caída.
 *
 * Los colores salen de custom properties para que el contexto los reasigne: la
 * cabecera sobre placa y la lámina de acceso encienden el filete y suben la
 * letra a hueso luminoso sin tocar el dibujo. Ver `.marca` en index.css.
 */
export function Marca({ size = 30, className, titulo }: Props) {
  return (
    <svg
      className={className ? `marca ${className}` : 'marca'}
      viewBox="0 0 32 32"
      width={size}
      height={size}
      role={titulo ? 'img' : undefined}
      aria-label={titulo}
      aria-hidden={titulo ? undefined : true}
      focusable="false"
    >
      {titulo && <title>{titulo}</title>}
      {/* Lámina */}
      <rect width="32" height="32" fill="var(--marca-placa)" />
      {/* Lomo */}
      <rect width="2.6" height="32" fill="var(--marca-acento)" />
      {/* Monograma */}
      <path
        d="M9.4 25.1V6.3L17.3 22.3 25.2 6.3V25.1"
        fill="none"
        stroke="var(--marca-trazo)"
        strokeWidth="3.6"
        strokeLinecap="butt"
        strokeLinejoin="miter"
        strokeMiterlimit="3"
      />
      {/* Filete: solo aparece sobre fondos oscuros, donde la lámina se funde. */}
      <rect x=".5" y=".5" width="31" height="31" fill="none" stroke="var(--marca-filete)" />
    </svg>
  )
}
