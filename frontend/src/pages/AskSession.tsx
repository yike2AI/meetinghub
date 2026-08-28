import { useQuery } from "@tanstack/react-query";
import { Input } from "antd";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { fmtDate } from "../lib";

type Msg = { role: string; content: string; citations?: any[]; trace?: string[] };

export function AskSession() {
  const { sessionId } = useParams();
  const sid = Number(sessionId);
  const [sp] = useSearchParams();
  const nav = useNavigate();
  const { data } = useQuery({ queryKey: ["sess", sid], queryFn: () => api.session(sid) });
  const { data: sessions } = useQuery({ queryKey: ["sessions"], queryFn: api.sessions });
  const { data: chips } = useQuery({
    queryKey: ["chips", data?.space_id],
    queryFn: () => api.suggestions(data.space_id),
    enabled: !!data?.space_id,
  });
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState(sp.get("q") || "");
  const [busy, setBusy] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const autoSent = useRef(false);
  useEffect(() => {
    if (data?.messages) {
      setMsgs(data.messages.map((m: any) => ({ role: m.role, content: m.content_md, citations: m.citations })));
    }
  }, [data]);
  useEffect(() => {
    const q = sp.get("q");
    if (q && data && !autoSent.current) {
      autoSent.current = true;
      void send(q);
    }
  }, [data, sp]);

  async function send(text: string) {
    if (!text.trim() || busy) return;
    setBusy(true);
    setInput("");
    setMsgs((m) => [...m, { role: "user", content: text }, { role: "assistant", content: "", citations: [], trace: [] }]);
    const res = await fetch(`/api/v1/agent/sessions/${sid}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: text }),
    });
    const reader = res.body?.getReader();
    const dec = new TextDecoder();
    let buf = "";
    if (!reader) {
      setBusy(false);
      return;
    }
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop() || "";
      for (const p of parts) {
        const ev = /event:\s*(\w+)/.exec(p)?.[1];
        const dataLine = p.split("\n").find((l) => l.startsWith("data:"));
        if (!ev || !dataLine) continue;
        const payload = JSON.parse(dataLine.slice(5).trim() || "{}");
        setMsgs((all) => {
          const copy = [...all];
          const last = copy[copy.length - 1];
          if (!last || last.role !== "assistant") return copy;
          if (ev === "delta") last.content += payload.text || "";
          if (ev === "status") last.trace = [...(last.trace || []), payload.text];
          if (ev === "citation") last.citations = [...(last.citations || []), payload];
          return copy;
        });
      }
    }
    setBusy(false);
    box.current?.scrollTo({ top: 99999, behavior: "smooth" });
  }

  return (
    <div className="flex gap-6 -mx-2">
      <aside className="w-[240px] shrink-0">
        <button className="btn-ghost w-full mb-4" onClick={() => nav("/ask")}>全部会话</button>
        <div className="text-[12px] text-text-sub mb-2">范围</div>
        <div className="badge bg-[#F0F5FF] text-brand mb-4">空间 #{data?.space_id}</div>
        <div className="text-[12px] text-text-sub mb-2">历史</div>
        <div className="space-y-1">
          {(sessions || []).map((s: any) => (
            <button
              key={s.id}
              onClick={() => nav(`/ask/${s.id}`)}
              className={`w-full text-left rounded-[12px] px-3 py-2 text-[13px] ${s.id === sid ? "bg-[#F0F5FF] text-brand" : "hover:bg-white"}`}
            >
              <div className="truncate">{s.title || `会话 #${s.id}`}</div>
              <div className="text-[11px] text-text-sub mt-0.5">{fmtDate(s.created_at)}</div>
            </button>
          ))}
        </div>
      </aside>
      <div className="flex-1 flex flex-col min-h-[72vh]">
        <div ref={box} className="flex-1 space-y-4 overflow-auto pb-4">
          {msgs.length === 0 && <div className="text-text-sub text-sm pt-8">点下方 chips，或直接问「上次会定了什么」。</div>}
          {msgs.map((m, i) => (
            <div key={i} className={`card p-5 ${m.role === "user" ? "bg-[#F0F5FF]" : ""}`}>
              <div className="text-[12px] text-text-sub mb-2">{m.role === "user" ? "你" : "复盘助手"}</div>
              {(m.trace || []).map((t, j) => (
                <div key={j} className="text-[12px] text-brand mb-1">{t}</div>
              ))}
              <div className="whitespace-pre-wrap leading-relaxed text-[15px]">{m.content}</div>
              {(m.citations || []).length > 0 && (
                <div className="mt-3 grid gap-2">
                  {m.citations!.map((c: any, k: number) => (
                    <Link key={k} to={`/meetings/${c.meeting_id}?seg=${c.segment_id}`} className="block p-3 rounded-[12px] border border-line hover:border-brand">
                      <div className="text-[12px] text-text-sub">引用 {c.index || k + 1} · {c.meeting_title}</div>
                      <div className="text-sm mt-1">{c.quote}</div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
        <div className="flex flex-wrap gap-2 mb-3">
          {(chips || []).map((c) => (
            <button key={c} className="badge bg-white border border-line hover:border-brand hover:text-brand px-3 py-1.5" onClick={() => send(c)}>
              {c}
            </button>
          ))}
        </div>
        <Input.Search enterButton={busy ? "生成中" : "发送"} disabled={busy} value={input} onChange={(e) => setInput(e.target.value)} onSearch={send} placeholder="例如：上次会定了什么 / XX 决策当时的依据 / 哪些承诺后来没下文" size="large" />
      </div>
    </div>
  );
}
