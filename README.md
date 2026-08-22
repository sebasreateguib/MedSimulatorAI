# MedSimulator AI

Simulador de casos clínicos con paciente virtual, especialistas consultores y tutor evaluador.
El estudiante no lee un caso en papel: lo **interroga**.

---

## 1. Qué hace

En vez de presentar un caso clínico escrito, el sistema lo convierte en una interacción:

- El estudiante hace **anamnesis** a un paciente virtual que responde según su historia oculta, sus síntomas y su estado emocional — sin revelar el diagnóstico.
- Puede **pedir laboratorios, ordenar imágenes, recetar y diagnosticar** mediante herramientas.
- Puede **llamar a un especialista** (cardiólogo, radiólogo) para interpretar un ECG o una imagen.
- Un **tutor** observa el razonamiento clínico en tiempo real, interviene ante errores peligrosos y produce una evaluación con rúbrica al final, penalizando pruebas innecesarias o invasivas según costo/efectividad.
- Cada dosis, criterio diagnóstico y decisión terapéutica se **valida contra un corpus documental (RAG)** antes de darse por buena.

### Mesa de estudio

Aparte de la simulación, cada usuario tiene una **biblioteca propia**:

- Sube **PDFs, imágenes, apuntes en txt/md y ofimática (docx, pptx, xlsx, html, epub)**. La ingesta corre en segundo plano —mismo pipeline que el corpus común: Docling → chunking → bge-m3— pero los chunks van a una tabla aparte (`chunks_documento`) filtrada por dueño.
- Las **imágenes pasan por OCR** (RapidOCR, local). Si no tienen texto legible —un ECG, un esquema, una radiografía— se describen con un **modelo multimodal** y se indexa esa descripción: es la única forma de que una imagen entre a un RAG textual. Se apaga con `VISION_PARA_IMAGENES=false`.
- **Conversa con un tutor que solo puede responder con ese material**. Cada afirmación se cita con `[n]`, y tocar la marca abre el archivo original en la página citada.
- **Genera mazos de flashcards** a partir de todo el material o de un tema, y los repasa con las peor sabidas primero.

Endpoints: `POST /biblioteca/documentos` (multipart), `GET /biblioteca/documentos`, `GET /biblioteca/documentos/{id}/archivo`, `POST /biblioteca/documentos/{id}/reintentar`, `POST /biblioteca/buscar`, `POST /estudio/chat` (SSE), `POST /estudio/mazos`, `POST /estudio/flashcards/{id}/repaso`.

Los archivos subidos viven en `MATERIAL_DIR` (por defecto `data/biblioteca/<usuario_id>/`, ya ignorado por git). Cada ingesta tiene un tope de `TIMEOUT_INGESTA_SEGUNDOS` (10 min por defecto); lo que falla queda en estado `error` con el motivo y se puede reintentar sin volver a subir el archivo.

---

## 2. Arquitectura

```
                      ┌──────────────────────────────────┐
   Estudiante ────────▶  Router de intención (Haiku/8B)  │
                      └────────────┬─────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
      ┌──────────────┐    ┌────────────────┐   ┌─────────────────┐
      │   Paciente   │    │  Especialista  │   │  Acción clínica │
      │  (roleplay)  │    │ (interconsulta)│   │    (tools)      │
      └──────────────┘    └────────────────┘   └────────┬────────┘
                                                        │
                                                        ▼
                                            ┌───────────────────────┐
                                            │  Validador RAG        │
                                            │  ¿dosis correcta?     │
                                            │  ¿criterio válido?    │
                                            └───────────────────────┘
                                                        │
      ┌─────────────────────────────────────────────────┘
      ▼
┌──────────────────────────────────────────────────────────────────┐
│  Tutor / Evaluador  —  async, fuera del loop síncrono            │
│  · escucha el stream de tool_use                                 │
│  · interrumpe solo si severidad >= alta                          │
│  · produce el scorecard final con structured output              │
└──────────────────────────────────────────────────────────────────┘
```

### Decisiones de arquitectura y su porqué

**El Tutor NO está en el loop síncrono.**
Si el tutor tuviera que responder antes de que el paciente hable, cada turno pagaría su latencia. En su lugar escucha los eventos `tool_use` que emite el estudiante y acumula el scorecard en paralelo. Solo interrumpe cuando la severidad lo justifica (prueba invasiva injustificada, dosis peligrosa). *Beneficio secundario:* también reduce el costo, porque el modelo caro no corre en cada turno.

**El Tutor evalúa al final, no incrementalmente.**
Evaluar en cada `tool_use` (~12 veces por sesión) multiplica el costo del agente más caro por 12 — de ~$0.19 a ~$0.90 por sesión. En su lugar: un chequeo barato con un modelo pequeño durante la sesión para detectar solo lo urgente, y la evaluación completa con rúbrica al cerrar.

**El Especialista NO interpreta imágenes reales (por ahora).**
Los hallazgos del ECG/radiografía vienen precargados como metadata del caso:

```json
{"ecg": "FA con respuesta ventricular rápida, 140 lpm, sin elevación del ST"}
```

El agente cardiólogo razona sobre esa descripción y la revela progresivamente según lo que el estudiante pregunte.

*Porqué:* la competencia que el simulador debe enseñar es **pedir la interconsulta correcta e interpretar la respuesta**, no hacer diagnóstico por imagen. Pedagógicamente equivalente, y evita el problema técnico más difícil del proyecto (los modelos abiertos con visión están muy por detrás en imagen médica). Si más adelante se quiere visión real, se cambia solo ese agente.

---

## 3. Stack

### Backend: Python + FastAPI

**Porqué Python y no TypeScript full-stack:** el ecosistema de RAG documental está en Python. Parsing de PDFs con estructura de tablas, chunking, embeddings locales, evaluación — todo tiene mejores herramientas aquí. El costo es tener dos servicios en vez de uno; se paga con creces.

### Frontend: Next.js 15 + TypeScript + Tailwind + shadcn/ui

SSE desde FastAPI para streaming token a token.

**Porqué importa el streaming:** ver al paciente "hablando" en tiempo real es la mitad de la experiencia. Una respuesta que aparece de golpe después de 4 segundos se siente como leer un caso en papel — exactamente lo que el proyecto intenta evitar.

### Base de datos: Postgres + pgvector

**Porqué no Pinecone/Weaviate/Qdrant:** ya necesitamos Postgres para usuarios, sesiones, transcripciones y scores. pgvector aguanta millones de chunks sin problema; agregar un servicio vectorial dedicado es complejidad operativa sin beneficio a esta escala. Si algún día el volumen lo justifica, se migra — el índice vectorial es la parte más fácil de mover.

### Ingesta de documentos: Docling

**Porqué NO `pymupdf`:** las guías de práctica clínica son mayoritariamente **tablas de dosificación, algoritmos de decisión y flowcharts**. `pymupdf` devuelve una tabla de dosis pediátricas como texto plano con las columnas intercaladas:

```
amoxicilina 500 250 mg/kg/día 90
```

Un chunk así es peor que no tener el documento: una dosis mal parseada es literalmente el peor bug posible en este producto.

**Porqué Docling y no LlamaParse:** Docling (IBM, open source) tiene reconocimiento de estructura de tablas muy sólido, corre local y es gratis. Correr local importa si algún día el proyecto toca datos reales de pacientes. LlamaParse es probablemente mejor, pero es un servicio externo de pago al que hay que subir los documentos. **Plan:** medir ambos con 20 páginas del corpus real antes de fijarlo. Si Docling no da la talla, se cambia.

**Para las páginas que Docling falle** (típicamente algoritmos gráficos, ~5–10%): mandar la imagen de la página a un modelo con visión pidiendo Markdown estructurado. Barato porque son pocas páginas.

**Red de seguridad obligatoria:** guardar el número de página de cada chunk. Cuando el sistema valide una dosis, la cita apunta al PDF original y el error de parsing se vuelve auditable en vez de invisible.

**Qué corre adentro de Docling.** No es un parser, son tres modelos locales:

| Modelo | Qué hace | Se enciende con |
|---|---|---|
| `docling-layout-heron` | detecta las regiones de la página: título, párrafo, tabla, caption | siempre |
| `TableFormer` (modo `accurate`) | reconstruye la estructura de cada tabla | `do_table_structure=True` |
| RapidOCR `PP-OCRv6` (det + cls + rec) | OCR de páginas escaneadas e imágenes | `do_ocr=True` |

**TableFormer es el que sostiene la promesa de arriba.** El layout solo dice "acá hay una tabla"; TableFormer dice cuántas filas y columnas tiene, cuáles celdas son encabezado y cuáles están combinadas. Es un resnet18 + decoder transformer entrenado sobre PubTabNet: recibe el recorte de la tabla y emite una secuencia de tags OTSL —`fcel` (celda con contenido), `ecel` (vacía), `ched` (encabezado de columna), `nl` (fin de fila)— más un bounding box por celda, que después se cruza contra el texto real del PDF para meter cada palabra en su lugar.

Eso es exactamente lo que devuelve `item.export_to_markdown()` en `docling_parser.py`. Y como `ChunkerClinico` nunca parte una tabla —queda como chunk único—, **la salida de TableFormer es literalmente un chunk del corpus**: se embebe así, se recupera así, y el validador la cita así. Un `rowspan` mal predicho pega la dosis al fármaco de la fila de al lado, y no hay ningún paso aguas abajo que lo detecte. Por eso el número de página por chunk no es opcional: es la única forma de volver al PDF y ver si la tabla se leyó bien.

Docling usa el modo `accurate` por defecto. Existe un `fast`, más liviano, pero acá la precisión de una tabla de dosis vale más que unos segundos de ingesta.

### Embeddings y reranking: locales

```
sentence-transformers + BAAI/bge-m3            # embeddings multilingües
FlagEmbedding      + BAAI/bge-reranker-v2-m3   # reranking
```

**Porqué local y no Voyage/Cohere:** `bge-m3` maneja español y terminología médica bien, y es gratis. Para un side project no hay razón para pagar embeddings. Corre aceptablemente en CPU al volumen del proyecto; en GPU vuela.

### Búsqueda: híbrida (BM25 + vectorial) + rerank

**Porqué no solo vectorial:** en medicina el match léxico exacto importa. `TFG`, `CHA₂DS₂-VASc`, `amiodarona`, `NYHA III` — la búsqueda semántica pura recupera documentos "sobre el tema" cuando lo que hace falta es el documento que menciona *ese* término exacto. BM25 cubre ese flanco; el reranker resuelve el orden final.

---

## 4. Modelos: multi-proveedor deliberado

```yaml
# config/agents.yaml
paciente:    {provider: groq,       model: llama-3.3-70b-versatile, temperature: 0.8}
router:      {provider: groq,       model: llama-3.1-8b-instant,    temperature: 0.0}
tutor:       {provider: anthropic,  model: claude-opus-5, effort: high}
validador:   {provider: anthropic,  model: claude-opus-5, citations: true}
especialista:{provider: openrouter, model: deepseek/deepseek-chat}
```

| Agente | Proveedor | Porqué |
|---|---|---|
| **Paciente** | Groq | Es el agente que más turnos genera y el único donde la latencia es parte de la experiencia. Groq entrega cientos de tokens/s. Barato y rápido gana sobre inteligente y lento aquí. |
| **Router** | Groq (8B) | Clasificación trivial de intención. Milisegundos, costo casi nulo. |
| **Validador RAG** | Anthropic | Es el punto donde una alucinación es **peligrosa**. Aquí no se escatima, y aquí es donde `citations` no tiene sustituto real. |
| **Tutor** | Anthropic | Razonamiento clínico + rúbrica estructurada. Corre async, la latencia no importa. |
| **Especialista** | OpenRouter | Razonamiento sobre hallazgos ya descritos en texto. Un modelo intermedio basta. |

### Porqué multi-proveedor y no uno solo

Este es un **proyecto de aprendizaje**, y cada camino enseña algo distinto:

- **Groq/OpenRouter** enseña la ingeniería real: orquestar agentes a mano, structured outputs sin garantías fuertes, verificación propia, manejar modelos que se equivocan más seguido.
- **Anthropic** enseña arquitectura de prompts, prompt caching, atribución verificable y evaluación con rúbrica — y da un **baseline de calidad** contra el cual medir.

Cuando el validador casero con DeepSeek falle, hay con qué comparar. Esa comparación — mismo prompt, mismo corpus, dos caminos — es probablemente el ejercicio más valioso del proyecto.

Groq y OpenRouter exponen API compatible con OpenAI, así que un solo cliente sirve para ambos:

```python
# llm/client.py
from openai import AsyncOpenAI

PROVIDERS = {
    "groq":       ("https://api.groq.com/openai/v1", settings.groq_key),
    "openrouter": ("https://openrouter.ai/api/v1",   settings.openrouter_key),
}
```

Cambiar de modelo o proveedor es editar una línea del YAML.

---

## 5. Features de la API de Anthropic que sí usamos

### Prompt caching

```python
system=[
    {"type": "text",
     "text": REGLAS_PACIENTE,
     "cache_control": {"type": "ephemeral", "ttl": "1h"}},
]
```

**Porqué está aquí aunque el paciente corra en Groq:** el prompt caching es una optimización **del lado del servidor** sobre el KV cache del modelo. No es reimplementable como ejercicio — lo único que se puede hacer del lado del cliente es cachear respuestas completas, que resuelve un problema distinto. Si se quiere aprender, tiene que ser contra un proveedor que lo ofrezca.

Lo que hay que aprender no es el código (son 3 líneas) sino la disciplina alrededor. El caché es un **match de prefijo exacto**: un solo byte distinto al inicio invalida todo lo posterior, **sin lanzar ningún error**.

```python
# ❌ Esto hace que el 100% de los requests sean cache miss, en silencio
system=[{"type": "text",
         "text": f"Fecha actual: {datetime.now()}\n\nEres un paciente...",
         "cache_control": {"type": "ephemeral"}}]
```

Reglas que el proyecto respeta:

1. El system prompt es **congelado** — nada de `datetime.now()`, UUIDs ni nombres de usuario interpolados.
2. La lista de `tools` se serializa **ordenada y estable** (renderiza en posición 0; cambiarla invalida todo).
3. Lo volátil va **después** del último breakpoint.
4. Se verifica en cada llamada:

```python
def verificar_cache(resp):
    u = resp.usage
    total = u.input_tokens + u.cache_creation_input_tokens + u.cache_read_input_tokens
    log.info("cache: escritos=%d leídos=%d sin_cachear=%d hit_rate=%.0f%%",
             u.cache_creation_input_tokens, u.cache_read_input_tokens,
             u.input_tokens, 100 * u.cache_read_input_tokens / total)
```

Este conocimiento **transfiere**: OpenAI, DeepSeek y Gemini tienen variantes del mismo mecanismo.

### Citations

```python
{"type": "document",
 "source": {"type": "text", "media_type": "text/plain", "data": chunk.texto},
 "title": f"{chunk.fuente} — p.{chunk.pagina}",
 "citations": {"enabled": True}}
```

La respuesta viene partida en bloques donde cada afirmación trae el texto literal citado y la página exacta:

```python
for bloque in resp.content:
    if bloque.type != "text":
        continue
    print(bloque.text)
    for cita in (bloque.citations or []):
        print(f"  └─ «{cita.cited_text}» — {cita.document_title}, p.{cita.start_page_number}")
```

**Porqué es el núcleo antialucinación:** no es una instrucción en el prompt ("cita tus fuentes"), es una restricción del decodificador. El modelo no puede inventar una cita.

### Structured outputs

Para el scorecard del tutor: JSON validado, sin parsear texto libre.

```python
class EvaluacionClinica(BaseModel):
    puntaje_total: int
    razonamiento_diagnostico: int
    costo_efectividad: int
    pruebas_innecesarias: list[str]
    errores_criticos: list[str]
    retroalimentacion: str

resp = client.messages.parse(..., output_format=EvaluacionClinica)
evaluacion = resp.parsed_output   # instancia validada
```

### El validador se implementa dos veces, a propósito

`rag/validador_nativo.py` (con `citations`) y `rag/validador_casero.py` (structured output + verificación por substring):

```python
class AfirmacionValidada(BaseModel):
    afirmacion: str
    chunk_id: str
    cita_literal: str
    veredicto: Literal["correcto", "incorrecto", "no_verificable"]

# La cita DEBE existir literalmente en el chunk
for a in respuesta.afirmaciones:
    if a.cita_literal not in chunks[a.chunk_id].texto:
        a.veredicto = "no_verificable"   # el modelo se lo inventó
```

**Porqué las dos:** la versión casera es lo que hay que escribir cuando el proveedor no ofrece `citations`. Atrapa la invención pura pero no detecta cuando el modelo cita algo real y lo interpreta mal. Tenerlas lado a lado permite medir exactamente cuánto vale la función nativa.

---

## 6. Lo que NO usamos, y porqué

### LangChain — descartado

Ahorra el loop de agente y el pegamento de RAG: unas 300 líneas. A cambio se pierde acceso directo a las funciones que **son el núcleo del proyecto**: `cache_control` con TTL en bloques específicos, `citations` con `page_location`, `effort` distinto por agente, hooks por turno del tool runner.

Envuelve todo eso en abstracciones que van uno o dos pasos detrás de la API, y rompe compatibilidad entre versiones menores con frecuencia. Para un proyecto donde el valor está en el control fino de la llamada, es el trade-off equivocado.

### LlamaIndex — descartado

Mejor que LangChain para RAG específicamente, pero el argumento es el mismo. Lo que aporta (ingestion pipeline, node parsers, retrievers) se reemplaza con `asyncpg` + `pgvector` y ~200 líneas propias — y esas 200 líneas se van a tocar constantemente: chunking por sección de guía clínica, metadata de fármaco/dosis, filtros por año, boosting de guías nacionales sobre internacionales. **Eso es lógica de dominio, no infraestructura.**

### Pydantic — SÍ, y no es opcional

FastAPI está construido sobre Pydantic, y es la vía nativa para structured outputs. Entra sí o sí.

---

## 7. Corpus documental — restricción legal

**Harrison y Sabiston están bajo copyright.** Ingerirlos a un vector store para un producto es un riesgo legal real, no un tecnicismo. **No van en el corpus.**

Fuentes que sí se pueden usar:

| Fuente | Qué aporta | Acceso |
|---|---|---|
| **GPC nacionales** (MINSA/IETSI Perú, CENETEC México) | Protocolos locales, dosificación | PDF público |
| **GPC internacionales** (NICE, WHO, AHA/ACC, ESC, ADA) | Criterios diagnósticos, algoritmos | PDF público |
| **PubMed** | Evidencia reciente | E-utilities API (`httpx.get` + XML) |
| **PubMed Central OA subset** | Texto completo, licencia abierta | API |
| **openFDA** | Labels de medicamentos, interacciones | API pública |
| **RxNorm / DrugBank (open subset)** | Normalización de nombres de fármacos | API |

Con GPC + PubMed OA + openFDA hay corpus suficiente y defendible. Los tratados quedan como referencia externa si la universidad tiene licencia institucional.

---

## 8. Costos

Sesión completa de 20 min (~60 turnos). Precios de Anthropic verificados; Groq/OpenRouter son **aproximados y cambian seguido**.

### Todo con Anthropic (referencia)

| Componente | Modelo | Costo |
|---|---|---|
| Paciente (60 turnos, caching 1h) | Sonnet 5 | $0.23 |
| Router (60 llamadas) | Haiku 4.5 | $0.05 |
| Validación RAG (~8 verificaciones) | Opus 5 | **$0.66** |
| Especialista (~3 interconsultas) | Opus 5 | $0.22 |
| Tutor (una vez, al final) | Opus 5 | $0.19 |
| **Total** | | **~$1.35** |

Dos cosas dominan y son fáciles de pasar por alto:

1. **Los tokens de thinking se facturan como output** ($25/MTok en Opus 5). Con `effort: "high"` en la validación RAG, el thinking solo son ~$0.30 — más que input y output juntos.
2. **El historial crece.** El turno 60 reprocesa todo lo anterior. El caching incremental lo amortigua (lecturas a 0.1×) pero no lo elimina.

### Todo con Groq + OpenRouter

| Componente | Modelo | Costo |
|---|---|---|
| Paciente | Llama 3.3 70B (Groq) | ~$0.10 |
| Router | Llama 3.1 8B (Groq) | ~$0.003 |
| Validación RAG | DeepSeek V3 | ~$0.017 |
| Especialista | DeepSeek V3 | ~$0.008 |
| Tutor | DeepSeek V3 | ~$0.01 |
| **Total** | | **~$0.14** |

~10× más barato. Nota que la pérdida del prompt caching **casi no duele aquí**: cuando el precio base es ~$0.59/MTok en vez de $5, reprocesar el historial cuesta centavos. El caching importa proporcionalmente más cuanto más caro es el modelo.

### La configuración híbrida elegida

**~$0.40/sesión.** Groq para el volumen de turnos, Anthropic solo donde una alucinación es peligrosa.

### Costo real de desarrollo

Desarrollando no se corren sesiones completas: se prueba un agente aislado con 5 turnos, se itera el prompt del validador con 3 chunks, se corre el tutor sobre una transcripción guardada. Cada iteración cuesta **$0.02–0.10**.

Cientos de iteraciones con Anthropic en validador + tutor: **~$20–30 en total**. Las sesiones largas end-to-end se corren contra Groq.

> **Nota sobre facturación:** la suscripción de Claude (Pro/Max) y la API de Anthropic son productos **separados**. Usar la API no consume la suscripción — es pago por uso con créditos aparte.

---

## 9. Dependencias

```
fastapi + uvicorn
pydantic + pydantic-settings
anthropic                 # SDK oficial
openai                    # cliente para Groq y OpenRouter (API compatible)
asyncpg + sqlalchemy
pgvector
docling                   # parsing de PDFs con estructura
sentence-transformers     # embeddings bge-m3
FlagEmbedding             # reranker bge-reranker-v2-m3
rank-bm25                 # búsqueda léxica
httpx                     # PubMed E-utilities, openFDA
langfuse                  # observabilidad, costo por sesión
alembic                   # migraciones
pytest + pytest-asyncio
```

Doce dependencias reales, sin frameworks de orquestación en el medio.

---

## 10. Estructura del proyecto

```
medsimulator/
├── app/
│   ├── main.py                    # FastAPI + endpoints SSE
│   ├── config.py                  # pydantic-settings
│   └── api/
│       ├── simulacion.py          # iniciar/continuar sesión
│       ├── evaluacion.py          # scorecard
│       ├── biblioteca.py          # material del usuario: subida + ingesta en background
│       └── estudio.py             # chat sobre el material (SSE) + flashcards
├── llm/
│   ├── client.py                  # factory multi-proveedor
│   ├── cache.py                   # helpers + verificar_cache()
│   └── schemas.py                 # modelos Pydantic compartidos
├── agents/
│   ├── orchestrator.py            # loop principal
│   ├── paciente.py
│   ├── router.py
│   ├── especialista.py
│   ├── tutor.py
│   ├── estudio.py                 # tutor sobre el material propio + generador de fichas
│   ├── vision.py                  # describe imágenes sin texto (único agente multimodal)
│   └── tools.py                   # pedir_laboratorio, recetar, diagnosticar...
├── rag/
│   ├── ingesta/
│   │   ├── docling_parser.py
│   │   ├── chunking.py            # por sección de guía clínica
│   │   ├── materiales.py          # ingesta del material subido (pdf/imagen/texto)
│   │   └── fuentes/               # pubmed.py, openfda.py, gpc.py
│   ├── embeddings.py              # bge-m3 local
│   ├── busqueda.py                # híbrida BM25 + vectorial + rerank
│   ├── busqueda_material.py       # ídem sobre el material del usuario, sin reranker
│   ├── validador_nativo.py        # con citations de Anthropic
│   └── validador_casero.py        # structured output + verificación
├── db/
│   ├── models.py
│   └── migrations/                # alembic (async), versions/ con el esquema
├── scripts/
│   └── precargar_modelos.py       # descarga y warmup de los modelos locales
├── config/
│   ├── agents.yaml                # asignación modelo↔agente
│   └── casos/                     # casos clínicos en YAML
├── tests/
└── frontend/                      # Next.js
```

---

## 11. Setup

Todos los comandos de backend corren **desde la raíz del repo**: los imports son
absolutos (`from medsimulator.app...`), así que el paquete tiene que resolverse
desde ahí.

### Primera vez

```bash
# Entorno virtual — vive en medsimulator/.venv
uv venv medsimulator/.venv && source medsimulator/.venv/bin/activate
uv pip install -r requirements.txt

# Variables de entorno
cp .env.example .env
#   GROQ_API_KEY=
#   OPENROUTER_API_KEY=
#   ANTHROPIC_API_KEY=
#   DATABASE_URL=
#   LANGFUSE_PUBLIC_KEY= / LANGFUSE_SECRET_KEY=

# Frontend
cd frontend && npm install && cd ..

# Modelos locales (~3,5 GB: bge-m3, layout, tablas y OCR).
# Opcional: la app también los carga sola al arrancar, pero acá se ve el progreso.
python scripts/precargar_modelos.py
```

### Levantar el proyecto

```bash
# 1. Postgres con pgvector (dejarlo corriendo; `docker ps` para verificar)
docker compose up -d db

# 2. Backend — puerto 8000, que es lo que proxea el frontend
source medsimulator/.venv/bin/activate
uvicorn medsimulator.app.main:app --reload --port 8000

# 3. Frontend — puerto 5173, en otra terminal
cd frontend && npm run dev
```

El esquema lo gobierna Alembic:

```bash
alembic upgrade head     # crea la extensión vector y todas las tablas
alembic revision --autogenerate -m "descripción"   # tras tocar db/models.py
```

La URL sale de `DATABASE_URL` (no de `alembic.ini`); `ALEMBIC_DATABASE_URL`
permite apuntar a otra base sin tocar la de la app. Si venís de una base creada
antes de las migraciones, `alembic stamp head` la marca como al día sin
reaplicar nada. `init_db()` sigue corriendo en el lifespan como red de
seguridad, pero solo crea tablas que falten: no altera las existentes.

Al arrancar, la app carga en segundo plano los modelos de ingesta. La primera
vez son varios minutos (descarga + warmup); después, unos segundos. Se apaga con
`PRECARGAR_MODELOS=false`.

El frontend pega a `/api` y Vite lo proxea a `http://localhost:8000`. Para
apuntar a otro backend, `VITE_API_PROXY_TARGET` en `frontend/.env`.

### Ingesta del corpus

```bash
python -m medsimulator.rag.ingesta.run --fuente gpc --path ./corpus/gpc/
```

---

## 12. Objetivos de aprendizaje

Lo que este proyecto enseña, ordenado por lo que cuesta aprenderlo en otro lado:

1. **Arquitectura de prompt caching** — orden de renderizado, invalidadores silenciosos, medición de hit rate. Transferible a cualquier proveedor.
2. **RAG con atribución verificable** — la diferencia entre "cita tus fuentes" en un prompt y una restricción del decodificador.
3. **Orquestación multi-agente a mano** — sin framework, entendiendo cada decisión de ruteo y cada handoff.
4. **Ingesta de documentos con estructura** — por qué un parser malo de PDFs es un bug de seguridad en un contexto médico.
5. **Búsqueda híbrida y reranking** — cuándo el match léxico gana al semántico.
6. **Comparación empírica de proveedores** — mismo prompt, mismo corpus, dos caminos, y medir la diferencia en vez de suponerla.
7. **Evaluación con rúbrica y structured outputs** — convertir juicio clínico en un scorecard reproducible.

---

## 13. Disclaimer

Herramienta **educativa**. No es un dispositivo médico, no emite diagnósticos reales y no debe usarse para tomar decisiones clínicas sobre pacientes reales. El corpus documental puede estar desactualizado respecto a la guía vigente.
