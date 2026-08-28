import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { entityTitle, type Entity } from "./lib";

const statusClass: Record<string, string> = {
  ingested: "bg-[#E8ECFF] text-brand",
  extracting: "bg-[#E8ECFF] text-brand",
  confirming: "bg-[#FFF7ED] text-[#F97316]",
  done: "bg-[#ECFDF5] text-ok",
  failed: "bg-[#FFF1F0] text-warn",
  unclaimed: "bg-[#F8FAFF] text-text-sub",
  pending: "bg-[#FFF7ED] text-[#F97316]",
  confirmed: "bg-[#ECFDF5] text-ok",
  auto_committed: "bg-[#FFF1F0] text-warn",
  ai_extracted: "bg-[#F0F5FF] text-brand",
  decision: "bg-[#F0F5FF] text-brand",
  commitment: "bg-[#ECFDF5] text-ok",
  risk: "bg-[#FFF1F0] text-warn",
  draft: "bg-[#F0F5FF] text-brand",
  finalized: "bg-[#ECFDF5] text-ok",
};

const statusLabel: Record<string, string> = {
  ingested: "已入库",
  extracting: "抽取中",
  confirming: "待确认",
  done: "完成",
  failed: "失败",
  unclaimed: "待认领",
  pending: "待确认",
  confirmed: "已确认",
  auto_committed: "AI 自动入库",
  ai_extracted: "待确认",
  decision: "决策",
  commitment: "承诺",
  risk: "风险",
  draft: "初稿",
  finalized: "定稿",
};

export function Badge({ status }: { status: string }) {
  return (
    <span className={`badge ${statusClass[status] || "bg-page text-text-sub"}`}>
      {statusLabel[status] || status}
    </span>
  );
}

export function PageHead({
  kicker,
  title,
  desc,
  extra,
}: {
  kicker?: string;
  title: string;
  desc?: string;
      extra?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-6 mb-8">
      <div>
        {kicker && <div className="text-[12px] tracking-[0.16em] uppercase text-brand font-semibold mb-2">{kicker}</div>}
        <h1 className="font-serif text-[32px] font-semibold leading-[1.3] text-text-main">{title}</h1>
        {desc && <p className="text-text-sub mt-2 text-[14px] max-w-[640px] leading-relaxed">{desc}</p>}
      </div>
      {extra}
    </div>
  );
}

export function Empty({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="card p-10 text-center">
      <div className="mx-auto mb-4 w-12 h-12 rounded-[12px] bg-[#F0F5FF] text-brand flex items-center justify-center">
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <rect x="4" y="5" width="16" height="14" rx="2" />
          <path d="M8 9h8M8 13h5" />
        </svg>
      </div>
      <div className="font-medium text-[15px]">{title}</div>
      {hint && <p className="text-text-sub text-sm mt-2 leading-relaxed max-w-[420px] mx-auto">{hint}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function EntityRow({ e, to }: { e: Entity; to?: string }) {
  const href = to || `/meetings/${e.meeting_id}?seg=${e.anchor_segment_ids?.[0] || ""}`;
  return (
    <Link to={href} className="row-card">
      <div className="flex items-center gap-2 flex-wrap">
        <Badge status={e.type} />
        <Badge status={e.status} />
        {e.auto_committed && <Badge status="auto_committed" />}
      </div>
      <div className="mt-2 font-medium text-[15px] leading-relaxed">{entityTitle(e)}</div>
      {(e.payload?.owner || e.payload?.decider || e.payload?.raiser) && (
        <div className="text-[12px] text-text-sub mt-1">
          {e.payload.decider || e.payload.owner || e.payload.raiser}
          {e.payload.due_date ? ` · ${e.payload.due_date}` : ""}
        </div>
      )}
    </Link>
  );
}
