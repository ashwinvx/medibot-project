"""
Module 5 — FastAPI Backend

Endpoints:
  POST /login                 Authenticate, return role-tagged JWT
  POST /chat                  Hybrid+Rerank RAG or SQL RAG with RBAC
  GET  /collections/{role}    Collections accessible to a role
  GET  /health                Health check

RBAC is enforced server-side: the role is read from the JWT, not from the
request body. An adversarial client cannot escalate privileges by sending
a different role in the payload.

Run from project root:
  uvicorn backend.main:app --reload --port 8000
"""

import os
import re
import logging
from typing import List

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from backend.auth import authenticate_user, create_access_token, decode_token
from backend.rag_chain import generate_rag_answer
from rag.retriever import HybridRetriever
from rag.reranker import Reranker
from rag.sql_rag import sql_rag_chain
from ingest.config import COLLECTION_CONFIG

log = logging.getLogger(__name__)

# ── Role configuration ───────────────────────────────────────────────────

SQL_RAG_ROLES = {"billing_executive", "admin"}

# Regex that flags analytical / database questions
_ANALYTICAL_RE = re.compile(
    r"\b(how many|count|total|sum|average|avg|highest|lowest|most|least|"
    r"breakdown|statistic|number of|how much|percentage|rate|ratio|"
    r"which department|which insurer|which campus|compare|versus|\bvs\b|"
    r"last month|this month|per department|per insurer|per category)\b",
    re.IGNORECASE,
)

# ── App ──────────────────────────────────────────────────────────────────

app = FastAPI(title="MediBot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

# Initialise retrieval models once at startup (expensive — do not move inside handlers)
retriever = HybridRetriever()
reranker = Reranker()

# ── Pydantic models ──────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    role: str


class ChatRequest(BaseModel):
    question: str


class SourceDoc(BaseModel):
    source_document: str
    section_title: str
    collection: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceDoc]
    retrieval_type: str   # "hybrid_rag" | "sql_rag"
    role: str
    rbac_blocked: bool = False


# ── Auth dependency ──────────────────────────────────────────────────────

def get_current_role(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    role = payload.get("role")
    if not role:
        raise HTTPException(status_code=401, detail="Token missing role claim")
    return role


# ── Endpoints ────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(username=user["username"], role=user["role"])
    return LoginResponse(access_token=token, token_type="bearer", role=user["role"])


@app.get("/collections/{role}")
def get_collections(role: str):
    accessible = [
        coll for coll, cfg in COLLECTION_CONFIG.items()
        if role in cfg["access_roles"]
    ]
    if not accessible:
        raise HTTPException(status_code=404, detail=f"Unknown role: {role}")
    return {"role": role, "collections": accessible}


@app.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    role: str = Depends(get_current_role),   # role always comes from JWT
):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # ── Route: SQL RAG ───────────────────────────────────────────────────
    if _ANALYTICAL_RE.search(question) and role in SQL_RAG_ROLES:
        log.info("Routing to SQL RAG | role=%s", role)
        answer = sql_rag_chain(question)
        return ChatResponse(
            answer=answer,
            sources=[],
            retrieval_type="sql_rag",
            role=role,
        )

    # ── Route: Hybrid RAG ────────────────────────────────────────────────
    log.info("Routing to Hybrid RAG | role=%s", role)

    accessible = [
        c for c, cfg in COLLECTION_CONFIG.items()
        if role in cfg["access_roles"]
    ]

    # RBAC filter is applied inside retriever at the Qdrant query level
    candidates = retriever.retrieve(question, role=role, top_k=10)

    if not candidates:
        return ChatResponse(
            answer=(
                f"As a {role}, I do not have access to the documents needed to answer this question. "
                f"I can only answer questions from the {', '.join(accessible)} collections."
            ),
            sources=[],
            retrieval_type="hybrid_rag",
            role=role,
            rbac_blocked=True,
        )

    top_chunks = reranker.rerank(question, candidates, top_k=3)
    answer = generate_rag_answer(
        question,
        top_chunks,
        role=role,
        accessible_collections=accessible,
    )

    # Detect when the LLM produced the RBAC fallback message
    rbac_blocked = answer.lower().startswith(f"as a {role.lower()},")

    sources = [
        SourceDoc(
            source_document=c["source_document"],
            section_title=c["section_title"],
            collection=c["collection"],
        )
        for c in top_chunks
    ]

    return ChatResponse(
        answer=answer,
        sources=sources if not rbac_blocked else [],
        retrieval_type="hybrid_rag",
        role=role,
        rbac_blocked=rbac_blocked,
    )
