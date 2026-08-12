import { useEffect, useState } from 'react'
import { useEsAngosto } from '../../hooks/useEsAngosto'
import Strands from '../wave'

/**
 * Paleta de la lámina: hueso, óxido, ámbar, verde clínico.
 * Los strands son luz aditiva — solo leen bien sobre la placa oscura.
 */
const PALETA = ['#EDE5D7', '#C4523F', '#A6702A', '#4A6B56']

/**
 * El shader normaliza las coordenadas por la ALTURA del lienzo, así que en una
 * pantalla angosta `uv.x` apenas llega a ±0.23 y la envolvente
 * `cos(uv.x · π · 1.3)` —que recién se cierra en |uv.x| ≥ 0.385— nunca toca
 * cero: la onda sale cortada por los dos costados.
 *
 * Bajar `scale` divide menos las coordenadas y hace que el ahusado entre en
 * pantalla. 0.6 es el techo que sale de esa cuenta (0.231 / 0.385); la
 * amplitud sube para compensar la figura más chica.
 */
const ONDA_ANCHA = { scale: 1.3, amplitude: 1.2, thickness: 0.62, count: 5 }
const ONDA_ANGOSTA = { scale: 0.58, amplitude: 1.5, thickness: 0.74, count: 4 }

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

/** Sin contexto WebGL no tiene sentido montar el canvas: queda el grabado estático. */
function soportaWebGL(): boolean {
  try {
    const canvas = document.createElement('canvas')
    return Boolean(canvas.getContext('webgl2') ?? canvas.getContext('webgl'))
  } catch {
    return false
  }
}

interface Props {
  onEntrar: () => void
}

export function Hero({ onEntrar }: Props) {
  const [animar, setAnimar] = useState(false)
  const angosto = useEsAngosto()
  const onda = angosto ? ONDA_ANGOSTA : ONDA_ANCHA

  // El hero es un canvas WebGL en loop: si el sistema pide menos movimiento,
  // no lo montamos y queda el grabado estático de respaldo.
  useEffect(() => {
    const hayWebGL = soportaWebGL()
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const aplicar = () => setAnimar(hayWebGL && !mq.matches)
    aplicar()
    mq.addEventListener('change', aplicar)
    return () => mq.removeEventListener('change', aplicar)
  }, [])

  return (
    <section className="hero">
      <div className="placa">
        <div className="placa__lienzo" aria-hidden="true">
          {animar && (
            <Strands
              className="placa__strands"
              colors={PALETA}
              count={onda.count}
              speed={0.32}
              amplitude={onda.amplitude}
              waviness={1.05}
              thickness={onda.thickness}
              glow={2.5}
              taper={2.4}
              intensity={0.72}
              saturation={1.25}
              scale={onda.scale}
            />
          )}
        </div>

        <div className="placa__contenido">
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

      </div>

      {/* Constantes al ingreso: rompe el borde de la lámina y cae sobre el papel. */}
      <div className="constantes">
        <dl className="constantes__fila">
          {CONSTANTES.map((c) => (
            <div key={c.rotulo} className="constante">
              <dt>{c.rotulo}</dt>
              <dd>
                <span className="constante__valor">{c.valor}</span>
                {c.unidad && <span className="constante__unidad">{c.unidad}</span>}
                <span className={`constante__nota${c.alterado ? ' constante__nota--alterado' : ''}`}>
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
    </section>
  )
}
