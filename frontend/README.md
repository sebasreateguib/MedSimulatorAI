# MedSimulator AI — Frontend

Vite + React + TypeScript. Landing page + cliente de simulación clínica contra la API de FastAPI.

## Correr

```bash
npm install
npm run dev          # http://localhost:5173
```

El backend se espera en `http://localhost:8000`:

```bash
# desde la raíz del repo
uvicorn medsimulator.app.main:app --reload
```

Vite proxea `/api/*` → backend (ver `vite.config.ts`), así que en el código no hay URLs
absolutas y no hace falta CORS en desarrollo. Para apuntar a otro host, copiá
`.env.example` a `.env` y ajustá `VITE_API_PROXY_TARGET` (dev) o `VITE_API_BASE_URL` (prod).

## Scripts

| Comando | Qué hace |
|---|---|
| `npm run dev` | Servidor de desarrollo con HMR |
| `npm run build` | `tsc -b` + build de producción a `dist/` |
| `npm run preview` | Sirve `dist/` |
| `npm run lint` | oxlint |

## Estructura

```
src/
├── components/
│   ├── landing/           # Landing: Hero (WebGL) + secciones
│   ├── wave.tsx           # Strands: fondo animado con ogl/WebGL
│   ├── SelectorCaso.tsx   # Catálogo de casos
│   ├── PanelChat.tsx      # Transcripción + autoscroll
│   ├── Mensaje.tsx        # Burbuja por rol (paciente/tutor/especialista)
│   ├── Composer.tsx       # Input con Enter/Shift+Enter
│   ├── PanelAcciones.tsx  # Atajos de herramientas clínicas
│   ├── Scorecard.tsx      # Evaluación del tutor
│   └── EstadoBackend.tsx  # Polling de /health
├── hooks/useSimulacion.ts # Estado de la sesión y del stream
├── lib/api.ts             # Cliente HTTP + parser SSE
├── lib/casos.ts           # Espejo local de config/casos/ (fallback)
├── styles/landing.css
└── types/index.ts
```

## Endpoints que consume

| Método | Ruta | Uso |
|---|---|---|
| `GET` | `/health` | Indicador de conexión |
| `GET` | `/simulacion/casos` | Catálogo (aún no existe → cae a `lib/casos.ts`) |
| `POST` | `/simulacion/iniciar` | `{caso_id}` → `{sesion_id}` |
| `POST` | `/simulacion/turno` | SSE token a token |
| `POST` | `/simulacion/finalizar?sesion_id=` | Dispara la evaluación |
| `GET` | `/evaluacion/{sesion_id}` | Scorecard |

## Notas de implementación

**SSE por `fetch`, no `EventSource`.** `EventSource` solo habla GET y `/simulacion/turno` es
POST con body. `lib/api.ts` lee el `ReadableStream`, parsea eventos `data:` y corta en `[DONE]`.
Como bonus, `AbortController` permite el botón "Detener".

**El scorecard acepta dos formas.** El backend hoy devuelve el mock
(`score_general` / `feedback`); `normalizarEvaluacion()` también acepta el `EvaluacionClinica`
definitivo de `medsimulator/llm/schemas.py`. Cuando el tutor real esté conectado, no hay que
tocar la UI.

**El hero respeta `prefers-reduced-motion`.** Si el sistema pide menos movimiento, el canvas
WebGL no se monta y queda el degradado estático de respaldo.
