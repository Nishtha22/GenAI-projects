# SparkRAG Assistant (LangChain RAG System)

Short: Retrieval-Augmented Generation (RAG) system for Apache Spark docs, using FAISS + BM25 + neural reranker and a local LLM runtime (Ollama) for generation.

## What this repo does
- Loads a FAISS index and document metadata from `data/faiss/` to perform vector retrieval.
- Uses a hybrid retriever (BM25 + FAISS + cross-encoder reranker) to get relevant context.
- Composes a prompt with chat history + retrieved context and sends it to a local LLM (Ollama) to generate answers.
- Exposes a FastAPI service with endpoints for single-turn QA and multi-turn chat with per-session chatbot instances.

## Important files
- `src/api/app.py` — FastAPI app and the simple chat UI endpoint at `/chat/ui`.
- `src/chatbot/langchain_chatbot.py` — per-session chatbot: prompt creation, retrieval, LLM calls, history management.
- `src/chatbot/session_manager.py` — session lifecycle and creation of `LangChainChatbot` instances.
- `src/retrieval/reranker_retriever.py` — hybrid retrieval pipeline.
- `configs/config.yaml` — main runtime configuration (embedding model, generation base_url, model name, reranker settings).


## Setup & run (development)
1. Create and activate a venv, install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Start a local LLM. The project is configured to use Ollama by default (local runtime). Start it like:

```bash
ollama serve &
```

3. Start the API server (dev reload recommended):

```bash
uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --reload
```

4. Open the chat UI in your browser:

```bash
open http://127.0.0.1:8000/chat/ui
```

5. Test the chat endpoint with curl:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello","session_id":"test1"}'
```

## Using other LLMs
The code instantiates an Ollama client by default. You can swap any LLM supported by LangChain by updating `src/chatbot/langchain_chatbot.py` or by passing an `llm` object into `LangChainChatbot`.

Options and notes:
- OpenAI (cloud): use `langchain.llms.OpenAI` and set `OPENAI_API_KEY` in env.
- Hugging Face Inference API: use `langchain.llms.HuggingFaceHub` or a compatible wrapper and set `HUGGINGFACEHUB_API_TOKEN`.
- Local runtimes: `gpt4all`, `llama.cpp`, `text-generation-webui` — either use LangChain wrappers or run a small local HTTP server and point `generation.base_url` to it.

Example: use OpenAI instead of Ollama (high-level):
1. Install OpenAI client (`pip install openai`) and LangChain extras.
2. Replace Ollama usage with:

```py
from langchain.llms import OpenAI
self.llm = OpenAI(model_name='gpt-4o-mini', openai_api_key=os.environ['OPENAI_API_KEY'])
```

3. Restart the API and ensure your API key is set.

## Using multiple sources beyond Spark
This project is already structured so you can add more than one knowledge source. The key idea is: collect documents from multiple sources, chunk and embed them, and store them in the same vector index.

### Recommended approach
1. Add your new content in a folder like:
   - `data/raw/spark/`
   - `data/raw/docs/`
   - `data/raw/faq/`
   - `data/raw/confluence/`
   - `data/raw/notebooks/`
2. Ingest all files through the same crawler/parser/chunker flow.
3. Merge everything into a single FAISS index or create one index per source and load them together.
4. Keep a `source` or `domain` field in each document metadata so the model can cite where the answer came from.

### Example
If you want to support Spark + internal docs + customer support FAQs, make each chunk include metadata like:

```python
{
    "source": "internal_docs",
    "source_url": "https://example.com/docs",
    "category": "support",
    "title": "Authentication Guide"
}
```

Then your retriever can fetch documents from all sources together. The prompt can say: “Answer using the most relevant docs from Spark, support FAQs, and internal guides.”

### Best practice for multi-source RAG
- Keep a clear `source` tag for each document.
- Add a `domain` or `tenant` attribute if you serve multiple teams or products.
- Store metadata in the vector store so citations can point back to the source.
- If the sources are very different in quality or style, consider using source-specific weighting in retrieval.

### Simple extension pattern
If you want to add a new source without changing the app logic much:

```python
# Example: add multiple folders for ingestion
folders = [
    "data/raw/spark",
    "data/raw/internal_docs",
    "data/raw/faqs",
    "data/raw/knowledge_base"
]
```

Then ingest all folders into one shared FAISS store.

### Important note
The current app is designed around a single vector store and retrieval pipeline. To support more than one source cleanly, the ideal next step is to:
- create a unified document list,
- preserve `source` metadata,
- optionally create separate indexes per source and merge them at query time.

This keeps answers grounded and lets you show the exact domain/source behind each result.

## Ingestion and rebuilding the FAISS index
If you change documents or need to rebuild the index, run the ingestion pipeline in `scripts/ingest_docs.py`. Ensure `data/faiss/` contains `index.faiss` and `documents.pkl`.

## API endpoints
- `GET /health` — health/status
- `POST /query` — single-turn question answering
- `POST /chat` — conversational chat (expects `message` and `session_id`)
- `GET /chat/ui` — simple browser UI for quick testing

## Notes & recommendations
- Use `uvicorn --reload` during development so edits are picked up automatically.
- If you switch to a cloud LLM, monitor cost and rate limits.
- Keep `data/faiss/index.faiss` and `data/faiss/documents.pkl` — they are required for retrieval.


