"""
LLM answer generation for the Hybrid RAG path.
Takes reranked top-3 chunks and produces a cited natural language answer.
"""

from typing import List, Optional
import anthropic

LLM_MODEL = "claude-haiku-4-5-20251001"
_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def generate_rag_answer(
    question: str,
    chunks: List[dict],
    role: str = "",
    accessible_collections: Optional[List[str]] = None,
) -> str:
    """
    Build a grounded prompt from the top-3 reranked chunks and call
    Claude to produce a cited answer.

    If the context is insufficient for the user's role, the LLM is
    instructed to return a clear RBAC-block message starting with
    "As a <role>," so callers can detect it reliably.
    """
    context_blocks = []
    for i, c in enumerate(chunks, 1):
        context_blocks.append(
            f"[{i}] Source: {c['source_document']} — {c['section_title']}\n{c['text']}"
        )
    context = "\n\n".join(context_blocks)

    collections_str = (
        ", ".join(accessible_collections) if accessible_collections else "your assigned"
    )

    rbac_fallback = (
        f"As a {role}, I do not have access to the documents needed to answer this question. "
        f"I can only answer questions from the {collections_str} collections."
    )

    prompt = (
        "You are MediBot, an internal knowledge assistant for MediAssist Health Network.\n"
        f"The user's role is: {role}.\n"
        f"This user has access to ONLY these document collections: {collections_str}.\n\n"
        "Answer the question using ONLY the context passages below.\n"
        "Cite sources by referencing [1], [2], [3] where relevant.\n\n"
        "IMPORTANT: If the context passages do not contain sufficient information to answer "
        "the question, respond with EXACTLY the following sentence and nothing else:\n"
        f'"{rbac_fallback}"\n\n'
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )

    response = _get_client().messages.create(
        model=LLM_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()
