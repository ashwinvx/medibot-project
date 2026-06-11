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


def generate_rag_answer(question: str, chunks: List[dict], role: str = "") -> str:
    """
    Build a grounded prompt from the top-3 reranked chunks and call
    Claude to produce a cited answer.
    """
    context_blocks = []
    for i, c in enumerate(chunks, 1):
        context_blocks.append(
            f"[{i}] Source: {c['source_document']} — {c['section_title']}\n{c['text']}"
        )
    context = "\n\n".join(context_blocks)

    role_line = f"The user's role is: {role}.\n" if role else ""

    prompt = (
        "You are MediBot, an internal knowledge assistant for MediAssist Health Network.\n"
        f"{role_line}"
        "Answer the question using ONLY the context passages below.\n"
        "Cite sources by referencing [1], [2], [3] where relevant.\n"
        "If the context does not contain enough information to answer the question, "
        "say clearly: 'As a {role}, I do not have access to documents that cover this topic. "
        "Please contact the relevant department for this information.'\n"
        "Be concise, factual, and avoid speculation.\n\n"
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
