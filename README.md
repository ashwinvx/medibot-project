# MediBot — Advanced RAG for MediAssist Health Network

An end-to-end Retrieval-Augmented Generation application built for the **Codebasics AI Engineering Bootcamp** assignment. MediBot answers staff questions from hospital documents and databases while enforcing role-based access control (RBAC) at the vector store level.

---

## Architecture

```
User (Next.js) ──► FastAPI ──► JWT RBAC ──┬──► Hybrid Retriever (Qdrant)
                                           │       dense (BGE) + sparse (BM25)
                                           │       RBAC filter at query level
                                           │       ↓ top-10 candidates
                                           │    Cross-Encoder Reranker
                                           │       ms-marco-MiniLM-L-6-v2
                                           │       top-10 → top-3
                                           │       ↓
                                           │    Claude Haiku (answer generation)
                                           │
                                           └──► SQL RAG Chain (analytical queries)
                                                   NL → SQL → Execute → Answer
```

## Modules

| # | Module | Key Technologies |
|---|--------|-----------------|
| 1 | Document Ingestion | Docling, HybridChunker, Qdrant |
| 2 | Hybrid Retriever + RBAC | Qdrant FusionQuery (RRF), BGE-small, BM25 |
| 3 | Cross-Encoder Reranker | sentence-transformers, ms-marco-MiniLM-L-6-v2 |
| 4 | SQL RAG | Claude Haiku, SQLite |
| 5 | FastAPI Backend | FastAPI, JWT (python-jose) |
| 6 | Next.js Frontend | Next.js 14, TypeScript, Tailwind CSS |

---

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- Docker

### 1. Start Qdrant

```bash
docker run -d -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage \
  qdrant/qdrant
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...
QDRANT_URL=http://localhost:6333
```

### 4. Run document ingestion

```bash
python -m ingest.ingest
```

This parses all PDFs with Docling, chunks them with HybridChunker, generates dense + sparse embeddings, and upserts ~1000 chunks into Qdrant with RBAC metadata.

### 5. Start the backend

```bash
uvicorn backend.main:app --reload --port 8000
```

### 6. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Demo Accounts

| Username | Password | Role | Accessible Collections |
|----------|----------|------|----------------------|
| `dr.mehta` | `doctor` | Doctor | general, clinical, nursing |
| `nurse.priya` | `nurse` | Nurse | general, nursing |
| `billing.ravi` | `billing_executive` | Billing Executive | general, billing |
| `tech.anand` | `technician` | Technician | general, equipment |
| `admin.sys` | `admin` | Admin | all collections |

---

## RBAC Design

Access control is enforced **at the Qdrant query level** — not in application code — using a `MatchValue` filter on the `access_roles` metadata field of every chunk. A user with role `nurse` physically cannot retrieve `clinical` or `billing` chunks regardless of what they ask.

When a query has no matching chunks for a role, MediBot returns a clear denial message:

> *"As a nurse, I do not have access to the documents needed to answer this question. I can only answer questions from the nursing, general collections."*

This message is displayed in amber in the UI and accompanied by an `rbac_blocked: true` flag in the API response.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/login` | Authenticate, returns JWT |
| `POST` | `/chat` | Ask a question (JWT required) |
| `GET` | `/collections/{role}` | List accessible collections for a role |
| `GET` | `/health` | Health check |

### Chat request

```bash
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the treatment for pneumonia?"}'
```

### Chat response

```json
{
  "answer": "...",
  "sources": [
    {"source_document": "treatment_protocols.pdf", "section_title": "...", "collection": "clinical"}
  ],
  "retrieval_type": "hybrid_rag",
  "role": "doctor",
  "rbac_blocked": false
}
```

---

## Testing Checklist

### RBAC

- `dr.mehta` asks "What is the treatment for pneumonia?" → clinical answer with sources
- `nurse.priya` asks "What is the treatment for pneumonia?" → amber RBAC denial (no clinical access)
- `tech.anand` asks "What is the drug dosage for hypertension?" → amber RBAC denial (no clinical access)
- `billing.ravi` asks "What are the billing codes for ICU?" → billing answer with sources
- `tech.anand` asks "How do I calibrate the ventilator?" → equipment answer with sources
- `admin.sys` can answer questions from all collections

### SQL RAG (billing_executive or admin only)

- "How many patients were admitted last month?"
- "What is the average billing amount for ICU patients?"
- "Which equipment has not been serviced in the last 6 months?"
- Response badge shows **SQL RAG** (green)

### Frontend

- Amber styling on RBAC-blocked responses
- Purple **Hybrid RAG** badge on document answers
- Green **SQL RAG** badge on analytical answers
- Collapsible source citations with document name and collection

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Claude Haiku (`claude-haiku-4-5-20251001`) |
| Vector Store | Qdrant (dense + sparse vectors) |
| Dense Embeddings | `BAAI/bge-small-en-v1.5` (384-dim, cosine) |
| Sparse Embeddings | `Qdrant/bm25` (fastembed) |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Document Parsing | Docling + HybridChunker |
| Database | SQLite (`mediassist.db`) |
| Backend | FastAPI + python-jose JWT |
| Frontend | Next.js 14 + TypeScript + Tailwind CSS |

---

## Project Structure

```
medibot-project/
├── ingest/
│   ├── config.py          # Collection config, model names, RBAC map
│   └── ingest.py          # Docling parse → chunk → embed → upsert
├── rag/
│   ├── retriever.py       # Hybrid retriever with RBAC filter
│   ├── reranker.py        # Cross-encoder reranker (top-10 → top-3)
│   └── sql_rag.py         # 3-step SQL RAG chain
├── backend/
│   ├── main.py            # FastAPI app, routing, RBAC detection
│   ├── auth.py            # JWT auth, demo users
│   └── rag_chain.py       # LLM answer generation
├── frontend/
│   ├── app/
│   │   ├── page.tsx       # Login page
│   │   └── chat/page.tsx  # Chat interface
│   └── lib/api.ts         # API client
├── data/mediassist_data/  # PDFs, Markdown files, SQLite DB
└── requirements.txt
```
