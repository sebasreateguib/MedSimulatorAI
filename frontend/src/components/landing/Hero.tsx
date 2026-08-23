import { useEffect, useRef, useState } from 'react'

const VIDEO = '/hero-video2.mp4'
/** Primer fotograma del clip: tapa la descarga y es el fondo fijo en angosto. */
const POSTER = '/hero-poster.webp'

const MOVIMIENTO_REDUCIDO = '(prefers-reduced-motion: reduce)'

/**
 * Constantes al ingreso del caso I (config/casos/fa_aguda.yaml).
 * Son los hallazgos que el estudiante obtiene si los pide: ninguno nombra
 * el diagnóstico, que es justamente lo que tiene que construir.
 */
const CONSTANTES = [
  { rotulo: 'Frecuencia ventricular', valor: '135', unidad: 'lpm', nota: 'Irregular', alterado: true },
  { rotulo: 'Potasio', valor: '3.4', unidad: 'mEq/L', nota: 'Bajo', alterado: true },
  { rotulo: 'Magnesio', valor: '1.6', unidad: 'mg/dL', nota: 'Bajo', alterado: true },
  { rotulo: 'Troponinas', valor: 'Neg.', unidad: '', nota: 'Sin necrosis', alterado: false },
]

interface Props {
  onEntrar: () => void
}

export function Hero({ onEntrar }: Props) {
  // Lazy y no `false`: arrancando en false el video se monta un frame y recién
  // el efecto lo apaga. Con movimiento reducido eso es justo lo que no se pide,
  // y además dispara la descarga del clip antes de desmontarlo.
  const [quieto, setQuieto] = useState(
    () => typeof window !== 'undefined' && window.matchMedia(MOVIMIENTO_REDUCIDO).matches,
  )
  const videoRef = useRef<HTMLVideoElement>(null)

  /**
   * El video se monta en todos los anchos; lo único que lo apaga es que el
   * sistema pida menos movimiento, y ahí queda el póster.
   *
   * En móvil no se montaba por dos razones que ya no valen: pesaba 9 MB (hoy
   * 2.77 y con el moov al frente, así que arranca sin bajar el archivo entero)
   * y el recorte 16:9 en vertical dejaba una faja sin sujeto (lo resuelve el
   * `object-position: 55%` del breakpoint).
   */
  const montarVideo = !quieto

  useEffect(() => {
    const mq = window.matchMedia(MOVIMIENTO_REDUCIDO)
    const aplicar = () => setQuieto(mq.matches)
    aplicar()
    mq.addEventListener('change', aplicar)
    return () => mq.removeEventListener('change', aplicar)
  }, [])

  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    // React escribe `muted` como propiedad y hay motores que evalúan la
    // política de autoplay antes de que llegue: sin forzarlo acá el clip se
    // queda clavado en el primer fotograma. Si igual lo bloquean, la promesa
    // rechaza y queda el póster, que es exactamente ese mismo fotograma.
    video.muted = true
    video.play().catch(() => {})
  }, [montarVideo])

  return (
    <section className="hero">
      <div className="placa">
        <div className="placa__lienzo" aria-hidden="true">
          {montarVideo ? (
            <video
              ref={videoRef}
              className="placa__video"
              src={VIDEO}
              poster={POSTER}
              autoPlay
              muted
              loop
              playsInline
              preload="metadata"
            />
          ) : (
            <img className="placa__video" src={POSTER} alt="" decoding="async" />
          )}
          {/* Velo: con la cartela sosteniendo el texto ya no tiene que tapar
              media pantalla. Solo baja un punto el conjunto y apaga el pie. */}
          <div className="placa__velo" />
        </div>

        <div className="placa__cartela">
          <p className="placa__rotulo" style={{ animationDelay: '0.05s' }}>
            Simulador Clínico IA · Razonamiento diagnóstico en tiempo real
          </p>

          <h1 className="hero__titulo">
            <span className="hero__linea" style={{ animationDelay: '0.14s' }}>
              El caso clínico
            </span>
            <span className="hero__linea" style={{ animationDelay: '0.24s' }}>
              no se lee.
            </span>
            <span className="hero__linea hero__linea--acento" style={{ animationDelay: '0.36s' }}>
              Se interroga.
            </span>
          </h1>

          <p className="hero__bajada" style={{ animationDelay: '0.5s' }}>
            El estudiante hace anamnesis a un paciente que responde según su historia oculta, pide
            estudios, llama al especialista y diagnostica. Un tutor observa el razonamiento y evalúa
            con rúbrica.
          </p>

          <div className="hero__acciones" style={{ animationDelay: '0.62s' }}>
            <button type="button" className="btn btn--luz" onClick={onEntrar}>
              Entrar al simulador
            </button>
            <a className="btn btn--contorno-luz" href="#procedimiento">
              Ver el procedimiento
            </a>
          </div>
        </div>

        {/* Constantes al ingreso: la fila de abajo de la lámina. Antes se le
            montaba al borde con un margen negativo; ahora es su pie. */}
        <div className="constantes">
          <dl className="constantes__fila">
            {CONSTANTES.map((c) => (
              <div key={c.rotulo} className="constante">
                <dt>{c.rotulo}</dt>
                <dd>
                  <span className="constante__valor">{c.valor}</span>
                  {c.unidad && <span className="constante__unidad">{c.unidad}</span>}
                  <span
                    className={`constante__nota${c.alterado ? ' constante__nota--alterado' : ''}`}
                  >
                    {c.nota}
                  </span>
                </dd>
              </div>
            ))}
          </dl>
          <p className="constantes__pie">
            Caso I · constantes al ingreso — el diagnóstico no se muestra, se construye
          </p>
        </div>
      </div>
    </section>
  )
}
