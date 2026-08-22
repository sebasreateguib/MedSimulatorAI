# Deploy

Notas sobre cómo llevar MedSimulator AI a un servidor, y en particular qué hacer
con los modelos que corren localmente.

Los LLM ya están afuera: paciente y router van por Groq, tutor y especialista por
OpenRouter. Los únicos modelos que viven en el servidor son los dos del RAG
—embeddings y reranking— más los de Docling para procesar PDFs. Todo lo de acá
abajo es sobre esos.

---

## 1. Lo que pesa hoy

| Componente | Disco | RAM residente |
|---|---|---|
| `bge-m3` (embeddings) | 2.1 GB | ~2.1 GB |
| `bge-reranker-v2-m3` | 2.1 GB | ~2.1 GB |
| Docling (layout + tablas + OCR) | ~0.5 GB | ~1 GB al procesar |
| PyTorch + el resto del venv | 1.6 GB | ~0.5 GB base |

**~6 GB de imagen y ~5 GB de RAM** con los dos modelos de RAG cargados. Eso es
una VM de 8 GB como piso, 16 GB para estar cómodo. No es descabellado: es una
instancia mediana, no un servidor de GPU.

Un detalle de la caché local: puede reportar 4.3 GB para `bge-m3` porque baja
`pytorch_model.bin` **y** `model.safetensors` —el mismo modelo dos veces—. En una
imagen bien armada eso no pasa.

---

## 2. La trampa: los workers de uvicorn

Esta es la que rompe deploys.

Cada worker de uvicorn es un **proceso separado**, y cada uno carga su propia
copia de los modelos en memoria. El `_buscador` global de
`medsimulator/app/api/biblioteca.py:58` es global *por proceso*, no por servidor.

```
uvicorn --workers 4   →   4 × 4.2 GB  =  17 GB de RAM  →  OOM
```

Si se deploya con la receta habitual de FastAPI (`--workers $(nproc)`), la VM se
muere. Con modelos locales hay que ir a **un solo worker** y escalar con hilos, o
sacar los modelos del proceso web.

---

## 3. Dónde caen los modelos

No todos pesan igual, porque no corren en el mismo momento.

**En el camino del request** (el usuario espera):

- `bge-m3` embebe la consulta — chat de estudio, búsqueda en biblioteca, y el
  validador en cada `recetar` / `diagnosticar`.
- El reranker reordena — solo en el validador.

**En segundo plano:** Docling procesa los PDF que sube el usuario. Pero
`biblioteca.py:318` usa `BackgroundTasks`, que corre **en el mismo proceso del
servidor web**. O sea que un PDF de 200 páginas come CPU mientras otros usuarios
chatean, y si el contenedor se reinicia a mitad de la ingesta el documento queda
en "procesando" para siempre.

---

## 4. Tres arquitecturas

**A — Todo en una VM.** Una imagen con los modelos horneados, un worker, warmup
al arrancar. Sirve para decenas de usuarios concurrentes.

**B — Servicio de inferencia aparte.** Un contenedor con
[Text Embeddings Inference](https://github.com/huggingface/text-embeddings-inference)
de Hugging Face sirviendo `bge-m3` y el reranker por HTTP; la app queda sin torch
(imagen de ~300 MB) y se puede escalar a N workers sin multiplicar la RAM. Es la
separación correcta cuando el proyecto crezca.

**C — API gestionada de embeddings.** Saca los modelos del todo. Pero la columna
es `Vector(1024)` (`medsimulator/db/models.py:79` y `:148`), atada a la dimensión
de `bge-m3`. Cambiar de modelo obliga a migrar la columna **y reingerir todo el
corpus**, porque los vectores viejos dejan de ser comparables. Hay que verificar
la dimensión del proveedor antes de decidir.

---

## 5. Si se va por la A: cuatro reglas

1. **Hornear los modelos en la imagen, nunca bajarlos al arrancar.** Para eso
   está `scripts/precargar_modelos.py`: va en el `Dockerfile`, no en el
   entrypoint. Bajarlos al boot son 5 GB de Hugging Face en cada redeploy y un
   arranque de varios minutos que puede fallar por rate limit.

2. **Fijar `HF_HOME`** a una ruta conocida (`/opt/models`) y que el usuario del
   contenedor pueda leerla. Si no, HF escribe en el `$HOME` del usuario del
   proceso, que en un contenedor suele no existir.

3. **Warmup al arrancar.** Los modelos cargan perezosamente: el primer usuario
   que busque paga 30-60 s. Un `lifespan` de FastAPI que embeba una frase tonta
   al inicio mueve ese costo al deploy.

4. **Sacar Docling a un worker aparte.** Es el que más pesa y el único que ya
   está fuera del request. Una cola simple bastaría; `BackgroundTasks` no
   sobrevive a un reinicio.

---

## 6. Recomendación

Para el tamaño que tiene el proyecto hoy: **VM de 16 GB, un contenedor, un
worker, modelos en la imagen, warmup al arrancar**, y Docling a un proceso aparte
cuando empiece a molestar.

---

## 7. Estado actual

- No hay `Dockerfile`.
- `docker-compose.yml` levanta solo la base (`pgvector/pgvector:pg16`); la app
  todavía corre a mano con uvicorn.

Lo que falta para deployar con la opción A: el `Dockerfile` con la precarga de
modelos, el `lifespan` de warmup y un `docker-compose` que incluya la app además
de la base.
