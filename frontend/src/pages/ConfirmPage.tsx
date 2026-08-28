import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Input, Modal, Select, message } from "antd";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { emptyPayload, entityTitle } from "../lib";
import { Badge } from "../ui";

function PayloadForm({ type, value, onChange }: { type: string; value: Record<string, any>; onChange: (v: Record<string, any>) => void }) {
  const set = (k: string, v: any) => onChange({ ...value, [k]: v });
  if (type === "commitment") {
    return (
      <div className="grid grid-cols-2 gap-3 mt-3">
        <Field label="事项" className="col-span-2"><Input value={value.item || ""} onChange={(e) => set("item", e.target.value)} /></Field>
        <Field label="责任人"><Input value={value.owner || ""} onChange={(e) => set("owner", e.target.value)} /></Field>
        <Field label="期限"><Input value={value.due_date || ""} onChange={(e) => set("due_date", e.target.value)} placeholder="YYYY-MM-DD 或原话" /></Field>
        <Field label="交付物" className="col-span-2"><Input value={value.deliverable || ""} onChange={(e) => set("deliverable", e.target.value)} /></Field>
      </div>
    );
  }
  if (type === "risk") {
    return (
      <div className="grid grid-cols-2 gap-3 mt-3">
        <Field label="风险描述" className="col-span-2"><Input.TextArea rows={3} value={value.description || ""} onChange={(e) => set("description", e.target.value)} /></Field>
        <Field label="提出人"><Input value={value.raiser || ""} onChange={(e) => set("raiser", e.target.value)} /></Field>
        <Field label="影响范围"><Input value={value.impact || ""} onChange={(e) => set("impact", e.target.value)} /></Field>
      </div>
    );
  }
  return (
    <div className="grid grid-cols-2 gap-3 mt-3">
      <Field label="结论" className="col-span-2"><Input.TextArea rows={2} value={value.conclusion || ""} onChange={(e) => set("conclusion", e.target.value)} /></Field>
      <Field label="拍板人"><Input value={value.decider || ""} onChange={(e) => set("decider", e.target.value)} /></Field>
      <Field label="依据" className="col-span-2"><Input.TextArea rows={2} value={value.rationale || ""} onChange={(e) => set("rationale", e.target.value)} /></Field>
    </div>
  );
}

function Field({ label, children, className = "" }: { label: string; children: import("react").ReactNode; className?: string }) {
  return (
    <label className={`block ${className}`}>
      <div className="text-[12px] text-text-sub mb-1">{label}</div>
      {children}
    </label>
  );
}

export function ConfirmPage() {
  const { id } = useParams();
  const mid = Number(id);
  const qc = useQueryClient();
  const { data: meeting } = useQuery({ queryKey: ["m", mid], queryFn: () => api.meeting(mid), refetchInterval: 3000 });
  const { data: segs } = useQuery({ queryKey: ["tr", mid], queryFn: () => api.transcript(mid) });
  const ents = meeting?.entities || [];
  const pending = ents.filter((e: any) => e.status === "ai_extracted");
  const deadline = meeting?.confirmation?.deadline_at;
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const left = useMemo(() => {
    if (!deadline) return "无倒计时";
    const ms = new Date(deadline).getTime() - now;
    if (ms <= 0) return "已超时，将自动入库";
    const m = Math.floor(ms / 60000);
    const s = Math.floor((ms % 60000) / 1000);
    return `${m}分${String(s).padStart(2, "0")}秒`;
  }, [deadline, now]);
  const [drafts, setDrafts] = useState<Record<number, Record<string, any>>>({});
  const [open, setOpen] = useState(false);
  const [manual, setManual] = useState({ type: "decision", text: "", seg: "" });
  const refresh = () => qc.invalidateQueries({ queryKey: ["m", mid] });

  return (
    <div>
      <div className="sticky top-0 z-10 bg-[#F8FAFF]/90 backdrop-blur border-b border-line py-4 mb-6 flex items-center justify-between">
        <div>
          <div className="font-semibold">{meeting?.title} · 确认</div>
          <div className="text-[13px] text-text-sub mt-1">
            进度 {ents.length - pending.length}/{ents.length} · 倒计时 {left}
          </div>
        </div>
        <div className="flex gap-2">
          <button className="btn-ghost" onClick={() => setOpen(true)}>补录</button>
          <button
            className="btn-primary"
            onClick={async () => {
              await api.confirmAll(mid);
              message.success("已全部确认");
              refresh();
            }}
          >
            一键全部确认
          </button>
        </div>
      </div>
      <div className="space-y-4">
        {ents.map((e: any) => {
          const quotes = (segs || []).filter((s: any) => (e.anchor_segment_ids || []).includes(s.id));
          const val = drafts[e.id] ?? e.payload ?? {};
          return (
            <div key={e.id} className="card p-5">
              <div className="flex items-center gap-2">
                <Badge status={e.type} />
                <Badge status={e.status} />
                {e.auto_committed && <Badge status="auto_committed" />}
                <span className="text-sm text-text-sub">{entityTitle(e)}</span>
              </div>
              <PayloadForm type={e.type} value={val} onChange={(v) => setDrafts({ ...drafts, [e.id]: v })} />
              <details className="mt-3 text-sm text-text-sub">
                <summary className="cursor-pointer text-brand">原文引用（{quotes.length}）</summary>
                {quotes.map((s: any) => (
                  <Link key={s.id} to={`/meetings/${mid}?seg=${s.id}`} className="block mt-2 p-2 rounded-[12px] bg-page">
                    {s.speaker_name}: {s.text}
                  </Link>
                ))}
              </details>
              <div className="flex gap-2 mt-4">
                <button className="btn-primary" onClick={async () => { await api.confirm(e.id); refresh(); }}>确认</button>
                <button
                  className="btn-ghost"
                  onClick={async () => {
                    await api.editEntity(e.id, drafts[e.id] ?? e.payload);
                    message.success("已修改并确认");
                    refresh();
                  }}
                >
                  保存修改
                </button>
                <button className="btn-ghost" onClick={async () => { await api.deleteEntity(e.id); refresh(); }}>删除</button>
              </div>
            </div>
          );
        })}
        {ents.length === 0 && <div className="card p-10 text-center text-text-sub">暂无实体。抽取完成后会出现在这里。</div>}
      </div>
      <Modal
        title="补录实体"
        open={open}
        onCancel={() => setOpen(false)}
        onOk={async () => {
          await api.addEntity(mid, {
            type: manual.type,
            payload: { ...emptyPayload(manual.type), ...(manual.type === "decision" ? { conclusion: manual.text } : manual.type === "commitment" ? { item: manual.text } : { description: manual.text }) },
            anchor_segment_ids: [Number(manual.seg)],
          });
          setOpen(false);
          refresh();
        }}
      >
        <Select className="w-full" value={manual.type} onChange={(v) => setManual({ ...manual, type: v })} options={[{ value: "decision", label: "决策" }, { value: "commitment", label: "承诺" }, { value: "risk", label: "风险" }]} />
        <Input className="mt-3" placeholder="锚点段落 id（打开档案页可见 seg 编号）" value={manual.seg} onChange={(e) => setManual({ ...manual, seg: e.target.value })} />
        <Input.TextArea className="mt-3" rows={3} placeholder="结论 / 事项 / 风险描述" value={manual.text} onChange={(e) => setManual({ ...manual, text: e.target.value })} />
      </Modal>
    </div>
  );
}
