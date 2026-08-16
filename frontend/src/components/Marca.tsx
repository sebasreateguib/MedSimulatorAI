interface Props {
  /** Lado en px. El trazo es geométrico, así que escala sin perder filo. */
  size?: number
  className?: string
  /** Si se pasa, la marca es contenido: se anuncia con este texto. Si no, es decorativa. */
  titulo?: string
}

/**
 * Marca de MedSimulator AI — "el cuadrante".
 *
 * Una lámina de tinta partida en cuatro por la cruz clínica, con el cuadrante
 * inferior derecho en óxido: el caso que todavía falta resolver. La cruz sangra
 * hasta el borde, así que a 16px sigue leyéndose como cruz y no como un ícono
 * flotando en una caja.
 *
 * Los colores salen de custom properties para que el contexto los reasigne: la
 * cabecera sobre placa y la lámina de acceso encienden el filete y suben los
 * acentos a sus versiones luminosas sin cambiar el dibujo. Ver `.marca` en
 * index.css.
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
      {/* Cuadrante inferior derecho */}
      <path d="M18.5 18.5H32V32H18.5z" fill="var(--marca-acento)" />
      {/* Cruz, sangrada a los cuatro bordes */}
      <path d="M13.5 0h5v32h-5zM0 13.5h32v5H0z" fill="var(--marca-cruz)" />
      {/* Filete: solo aparece sobre fondos oscuros, donde la lámina se funde. */}
      <rect x=".5" y=".5" width="31" height="31" fill="none" stroke="var(--marca-filete)" />
    </svg>
  )
}
