"use client";

import { useState, useEffect, useRef, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { sendChat, getCollections, Source } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────

interface Message {
  id: string;
  type: "user" | "bot";
  text: string;
  sources?: Source[];
  retrieval_type?: "hybrid_rag" | "sql_rag";
}

// ── Role badge colours ────────────────────────────────────────────────────

const ROLE_COLORS: Record<string, string> = {
  doctor:            "bg-blue-100 text-blue-800",
  nurse:             "bg-green-100 text-green-800",
  billing_executive: "bg-amber-100 text-amber-800",
  technician:        "bg-purple-100 text-purple-800",
  admin:             "bg-red-100 text-red-800",
};

const ROLE_LABELS: Record<string, string> = {
  doctor:            "Doctor",
  nurse:             "Nurse",
  billing_executive: "Billing Executive",
  technician:        "Technician",
  admin:             "Admin",
};

const COLLECTION_ICONS: Record<string, string> = {
  general:   "📋",
  clinical:  "🩺",
  nursing:   "💉",
  billing:   "💳",
  equipment: "🔧",
};

// ── Source citations component ────────────────────────────────────────────

function SourceList({ sources }: { sources: Source[] }) {
  const [open, setOpen] = useState(false);
  if (!sources.length) return null;
  return (
    <div className="mt-3 border-t border-gray-100 pt-3">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 transition-colors"
      >
        <span>{open ? "▾" : "▸"}</span>
        <span>{sources.length} source{sources.length > 1 ? "s" : ""}</span>
      </button>
      {open && (
        <ul className="mt-2 space-y-1.5">
          {sources.map((s, i) => (
            <li key={i} className="flex items-start gap-2 text-xs text-gray-500">
              <span className="mt-0.5 shrink-0 w-4 h-4 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center font-medium text-[10px]">
                {i + 1}
              </span>
              <span>
                <span className="font-medium text-gray-700">{s.source_document}</span>
                {s.section_title && (
                  <span className="text-gray-400"> · {s.section_title}</span>
                )}
                <span className="ml-1 text-[10px] bg-gray-100 text-gray-400 px-1.5 py-0.5 rounded-full">
                  {s.collection}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Bot message card ──────────────────────────────────────────────────────

function BotMessage({ msg }: { msg: Message }) {
  const isRbacBlock =
    msg.text.toLowerCase().includes("do not have access") ||
    msg.text.toLowerCase().includes("not have access to");

  return (
    <div className="flex gap-3 max-w-3xl">
      {/* Avatar */}
      <div className="shrink-0 w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm font-bold">
        M
      </div>

      <div className="flex-1 min-w-0">
        <div
          className={`rounded-2xl rounded-tl-sm px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
            isRbacBlock
              ? "bg-orange-50 border border-orange-200 text-orange-800"
              : "bg-white border border-gray-200 text-gray-800"
          }`}
        >
          {msg.text}
        </div>

        {/* Retrieval type badge */}
        {msg.retrieval_type && (
          <div className="mt-1.5 flex items-center gap-2">
            <span
              className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${
                msg.retrieval_type === "sql_rag"
                  ? "bg-emerald-100 text-emerald-700"
                  : "bg-violet-100 text-violet-700"
              }`}
            >
              {msg.retrieval_type === "sql_rag" ? "SQL RAG" : "Hybrid RAG"}
            </span>
          </div>
        )}

        {/* Source citations */}
        {msg.sources && msg.sources.length > 0 && (
          <div className="mt-1">
            <SourceList sources={msg.sources} />
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main chat page ────────────────────────────────────────────────────────

export default function ChatPage() {
  const router = useRouter();
  const [token, setToken]           = useState<string | null>(null);
  const [role, setRole]             = useState<string>("");
  const [username, setUsername]     = useState<string>("");
  const [collections, setCollections] = useState<string[]>([]);
  const [messages, setMessages]     = useState<Message[]>([]);
  const [input, setInput]           = useState("");
  const [loading, setLoading]       = useState(false);
  const bottomRef                   = useRef<HTMLDivElement>(null);

  // Load auth from localStorage
  useEffect(() => {
    const t = localStorage.getItem("token");
    const r = localStorage.getItem("role");
    const u = localStorage.getItem("username");
    if (!t || !r) { router.push("/"); return; }
    setToken(t);
    setRole(r);
    setUsername(u ?? "");
    getCollections(r).then(setCollections);

    setMessages([
      {
        id: "welcome",
        type: "bot",
        text: `Hello! I'm MediBot, your internal knowledge assistant. I can answer questions from the documents and databases you have access to as a ${ROLE_LABELS[r] ?? r}. How can I help you?`,
      },
    ]);
  }, [router]);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend(e: FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (!q || !token) return;

    const userMsg: Message = { id: Date.now().toString(), type: "user", text: q };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const data = await sendChat(q, token);
      const botMsg: Message = {
        id: (Date.now() + 1).toString(),
        type: "bot",
        text: data.answer,
        sources: data.sources,
        retrieval_type: data.retrieval_type,
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (err: unknown) {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          type: "bot",
          text: err instanceof Error ? err.message : "An error occurred. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleLogout() {
    localStorage.clear();
    router.push("/");
  }

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">

      {/* ── Sidebar ─────────────────────────────────────────────────── */}
      <aside className="w-64 shrink-0 bg-white border-r border-gray-200 flex flex-col">
        {/* Brand */}
        <div className="p-5 border-b border-gray-100">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">
              M
            </div>
            <div>
              <div className="font-semibold text-gray-900 text-sm">MediBot</div>
              <div className="text-[11px] text-gray-400">MediAssist Health Network</div>
            </div>
          </div>
        </div>

        {/* User info */}
        <div className="p-4 border-b border-gray-100">
          <div className="text-xs text-gray-400 font-medium uppercase tracking-wide mb-2">
            Signed in as
          </div>
          <div className="font-mono text-sm text-gray-700 truncate">{username}</div>
          <div className="mt-2">
            <span
              className={`inline-block text-xs font-medium px-2.5 py-1 rounded-full ${
                ROLE_COLORS[role] ?? "bg-gray-100 text-gray-600"
              }`}
            >
              {ROLE_LABELS[role] ?? role}
            </span>
          </div>
        </div>

        {/* Accessible collections */}
        <div className="p-4 flex-1 overflow-y-auto">
          <div className="text-xs text-gray-400 font-medium uppercase tracking-wide mb-3">
            Accessible collections
          </div>
          <ul className="space-y-1.5">
            {collections.map((c) => (
              <li
                key={c}
                className="flex items-center gap-2 text-sm text-gray-600 px-2 py-1.5 rounded-lg bg-gray-50"
              >
                <span>{COLLECTION_ICONS[c] ?? "📄"}</span>
                <span className="capitalize">{c}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Logout */}
        <div className="p-4 border-t border-gray-100">
          <button
            onClick={handleLogout}
            className="w-full text-sm text-gray-500 hover:text-red-600 hover:bg-red-50 px-3 py-2 rounded-lg transition-colors text-left"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* ── Chat area ───────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="bg-white border-b border-gray-200 px-6 py-4 shrink-0">
          <h1 className="font-semibold text-gray-800">Chat</h1>
          <p className="text-xs text-gray-400 mt-0.5">
            Ask questions from your accessible document collections
          </p>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
          {messages.map((msg) =>
            msg.type === "user" ? (
              /* User bubble */
              <div key={msg.id} className="flex justify-end">
                <div className="max-w-xl bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed">
                  {msg.text}
                </div>
              </div>
            ) : (
              /* Bot message */
              <BotMessage key={msg.id} msg={msg} />
            )
          )}

          {/* Typing indicator */}
          {loading && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm font-bold shrink-0">
                M
              </div>
              <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3">
                <div className="flex gap-1 items-center h-4">
                  <span className="w-2 h-2 bg-gray-300 rounded-full animate-bounce [animation-delay:-0.3s]" />
                  <span className="w-2 h-2 bg-gray-300 rounded-full animate-bounce [animation-delay:-0.15s]" />
                  <span className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" />
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="bg-white border-t border-gray-200 px-6 py-4 shrink-0">
          <form onSubmit={handleSend} className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
              placeholder="Ask a question…"
              className="flex-1 px-4 py-2.5 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm disabled:bg-gray-50"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-200 disabled:text-gray-400 text-white px-5 py-2.5 rounded-xl font-medium text-sm transition-colors"
            >
              Send
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
