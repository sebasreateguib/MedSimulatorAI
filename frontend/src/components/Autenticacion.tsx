import { useState } from 'react'

interface Props {
  onEntrar: (email: string, password: string) => Promise<void>
  onRegistrarse: (username: string, email: string, password: string) => Promise<void>
  onVolver: () => void
}

type Modo = 'login' | 'registro'

const MIN_PASSWORD = 8

/** Las tres estaciones del caso: dan cuerpo a la lámina y explican qué se entra a hacer. */
const ESTACIONES = [
  {
    n: '01',
    titulo: 'Anamnesis',
    texto: 'El paciente responde según una historia oculta. Nada se ofrece: todo se pregunta.',
  },
  {
    n: '02',
    titulo: 'Estudios e interconsulta',
    texto: 'Laboratorio, imágenes y el especialista de guardia, cuando el razonamiento los pide.',
  },
  {
    n: '03',
    titulo: 'Evaluación con rúbrica',
    texto: 'Un tutor observa el recorrido completo y devuelve puntaje por dimensión.',
  },
]

export function Autenticacion({ onEntrar, onRegistrarse, onVolver }: Props) {
  const [modo, setModo] = useState<Modo>('login')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  const esRegistro = modo === 'registro'

  const cambiarModo = () => {
    setModo(esRegistro ? 'login' : 'registro')
    setError(null)
  }

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault()
    if (enviando) return

    if (esRegistro && password.length < MIN_PASSWORD) {
      setError(`La contraseña debe tener al menos ${MIN_PASSWORD} caracteres.`)
      return
    }

    setEnviando(true)
    setError(null)
    try {
      if (esRegistro) {
        await onRegistrarse(username.trim(), email.trim(), password)
      } else {
        await onEntrar(email.trim(), password)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo completar la operación.')
      setEnviando(false)
    }
  }

  return (
    <div className="acceso">
      {/* Lámina: el lado oscuro sostiene el relato; el formulario queda limpio sobre papel. */}
      <aside className="acceso__lamina">
        <div className="acceso__marca">
          <span className="logotipo" role="img" aria-label="MedSimulator AI" />
        </div>

        <div className="acceso__discurso">
          <p className="acceso__rotulo-luz">
            Simulador clínico IA · Razonamiento diagnóstico en tiempo real
          </p>
          <h2 className="acceso__lema">
            <span>El caso clínico</span>
            <span>no se lee.</span>
            <span className="acceso__lema--acento">Se interroga.</span>
          </h2>
        </div>

        <ol className="acceso__estaciones">
          {ESTACIONES.map((e) => (
            <li key={e.n} className="acceso__estacion">
              <span className="acceso__estacion-n">{e.n}</span>
              <div>
                <h3>{e.titulo}</h3>
                <p>{e.texto}</p>
              </div>
            </li>
          ))}
        </ol>

        <p className="acceso__pie">
          Tus sesiones, puntajes y métricas quedan asociados a tu cuenta.
        </p>
      </aside>

      <main className="acceso__forma">
        <button type="button" className="acceso__volver rotulo" onClick={onVolver}>
          ← Volver al inicio
        </button>

        <div className="acceso__columna">
          <p className="rotulo acceso__paso">
            {esRegistro ? 'Registro · cuenta nueva' : 'Acceso · cuenta existente'}
          </p>

          <h1 className="acceso__titulo">
            {esRegistro ? 'Crear cuenta' : 'Entrar al simulador'}
          </h1>
          <p className="acceso__bajada">
            {esRegistro
              ? 'Un minuto y quedás con historial propio de casos, evaluaciones y progreso.'
              : 'Ingresá para retomar tu historial de casos y tus métricas.'}
          </p>

          <form className="acceso__form" onSubmit={enviar}>
            {esRegistro && (
              <label className="campo">
                <span className="rotulo">Nombre de usuario</span>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  minLength={3}
                  maxLength={40}
                  autoComplete="username"
                  placeholder="ej. sreategui"
                />
              </label>
            )}

            <label className="campo">
              <span className="rotulo">Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                placeholder="tu@correo.com"
              />
            </label>

            <label className="campo">
              <span className="rotulo">Contraseña</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={esRegistro ? MIN_PASSWORD : undefined}
                autoComplete={esRegistro ? 'new-password' : 'current-password'}
                placeholder={esRegistro ? `Mínimo ${MIN_PASSWORD} caracteres` : '••••••••'}
              />
            </label>

            {error && (
              <div className="alerta" role="alert">
                <span>{error}</span>
              </div>
            )}

            <button type="submit" className="btn btn--primario acceso__submit" disabled={enviando}>
              {enviando ? 'Procesando…' : esRegistro ? 'Crear cuenta' : 'Entrar'}
            </button>
          </form>

          <p className="acceso__alterno">
            {esRegistro ? '¿Ya tenés cuenta?' : '¿Todavía no tenés cuenta?'}{' '}
            <button type="button" onClick={cambiarModo}>
              {esRegistro ? 'Iniciar sesión' : 'Registrate'}
            </button>
          </p>
        </div>
      </main>
    </div>
  )
}
