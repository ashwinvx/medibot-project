const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Source {
  source_document: string;
  section_title: string;
  collection: string;
}

export interface ChatResponse {
  answer: string;
  sources: Source[];
  retrieval_type: "hybrid_rag" | "sql_rag";
  role: string;
  rbac_blocked: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: string;
}

export async function login(
  username: string,
  password: string
): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Invalid credentials");
  }
  return res.json();
}

export async function sendChat(
  question: string,
  token: string
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Chat request failed");
  }
  return res.json();
}

export async function getCollections(role: string): Promise<string[]> {
  const res = await fetch(`${API_BASE}/collections/${role}`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.collections ?? [];
}
