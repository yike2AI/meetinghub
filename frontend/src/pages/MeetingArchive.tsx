import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { entityTitle, fmtDate, fmtMs } from "../lib";
import { Badge, Empty, PageHead } from "../ui";

const KIND_LABEL: Record<string, string> = {
  platform_summary: "总结",
  platform_todo: "待办",
  platform_chapter: "章节大纲",
  generated_summary: "要点大纲 + 结论 / 待办",
};

function summaryBadge(artifacts: any[], source?: string) {
  const platform = (artifacts || []).some((a) => String(a.kind || "").startsWith("platform_"));
  if (platform) {
    if (source === "feishu") return "飞书妙记";
    if (source === "dingtalk") return "钉钉听记";
    return "平台纪要";
  }
  if ((artifacts || []).some((a) => a.kind === "generated_summary")) return "本系统补写";
  return null;
}

function SummaryPane({ artifacts, source }: { artifacts: any[]; source?: string }) {
  const platform = (artifacts || []).filter((a) => String(a.kind || "").startsWith("platform_") && a.content);
  const generated = (artifacts || []).filter((a) => a.kind === "generated_summary" && a.content);
  const items = platform.length ? platform : generated;
  const badge = summaryBadge(artifacts, source);
  if (!items.length) {
    return <Empty title="还没有 AI 总结" hint="飞书/钉钉有纪要会显示在这里；没有则在抽取时由本系统按「要点大纲 + 结论/待办」补写。" />;
  }
  return (
    <div className="space-y-3">
      {badge && (
        <div className="text-[12px] text-text-sub">
          来源 <span className="badge bg-[#E8ECFF] text-brand">{badge}</span>
        </div>
      )}
      {items.map((a: any) => (
        <div key={a.id || a.kind} className="card p-5">
          <div className="text-[12px] tracking-[0.12em] uppercase text-brand font-semibold mb-3">
            {KIND_LABEL[a.kind] || a.kind}
          </div>
          <div className="text-[15px] leading-relaxed whitespace-pre-wrap">{a.content}</div>
        </div>
      ))}
    </div>
  );
}

export function MeetingArchive() {
  const { id } = useParams();
  const mid = Number(id);
  const [sp] = useSearchParams();
  const hit = Number(sp.get("seg") || 0);
  const [tab, setTab] = useState<"summary" | "original">("summary");
  const { data: meeting } = useQuery({ queryKey: ["m", mid], queryFn: () => api.meeting(mid), refetchInterval: 5000 });
  const { data: segs } = useQuery({ queryKey: ["tr", mid], queryFn: () => api.transcript(mid) });
  const refs = useRef<Record<number, HTMLDivElement | null>>({});
  useEffect(() => {
    if (hit && refs.current[hit]) {
      setTab("original");
      refs.current[hit]?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [hit, segs]);

  return (
    <div>
      <PageHead
        title={meeting?.title || "会议档案"}
        desc={`${fmtDate(meeting?.held_at)} · 来源 ${meeting?.source || ""}`}
        extra={
          <div className="flex gap-2">
            {meeting?.status && <Badge status={meeting.status} />}
            <Link className="btn-ghost" to={`/meetings/${mid}/confirm`}>去确认</Link>
            <button className="btn-primary" onClick={() => api.reExtract(mid)}>重跑抽取</button>
          </div>
        }
      />
      <div className="flex gap-6 items-start">
        <div className="w-[65%] space-y-3">
          <div className="flex gap-2">
            <button className={tab === "summary" ? "archive-tab archive-tab-active" : "archive-tab"} onClick={() => setTab("summary")}>AI 总结</button>
            <button className={tab === "original" ? "archive-tab archive-tab-active" : "archive-tab"} onClick={() => setTab("original")}>原文</button>
          </div>
          {tab === "summary" ? (
            <SummaryPane artifacts={meeting?.artifacts || []} source={meeting?.source} />
          ) : (
            <>
              {(segs || []).map((s: any) => (
                <div
                  key={s.id}
                  ref={(el) => { refs.current[s.id] = el; }}
                  className={`card p-4 ${hit === s.id ? "seg-hit" : ""}`}
                >
                  <div className="text-[12px] text-text-sub mb-1">
                    {s.speaker_name || "发言人"} · {fmtMs(s.start_ms)} · seg {s.id}
                  </div>
                  <div className="text-[15px] leading-relaxed">{s.text}</div>
                </div>
              ))}
              {(segs || []).length === 0 && <div className="card p-10 text-center text-text-sub">逐字稿加载中或尚未入库</div>}
            </>
          )}
        </div>
        <aside className="w-[35%] sticky top-8 space-y-3">
          <div className="card p-5">
            <div className="font-semibold mb-1">核心资产</div>
            <div className="text-[12px] text-text-sub mb-3">决策 / 承诺 / 风险。点击跳到原文并高亮</div>
            {(meeting?.entities || []).map((e: any) => (
              <Link key={e.id} to={`/meetings/${mid}?seg=${e.anchor_segment_ids?.[0] || ""}`} className="block py-3 border-b border-line last:border-0 hover:translate-x-1 transition-transform">
                <Badge status={e.type} /> {e.auto_committed && <Badge status="auto_committed" />}
                <div className="mt-1 text-sm leading-relaxed">{entityTitle(e)}</div>
              </Link>
            ))}
            {(meeting?.entities || []).length === 0 && <div className="text-text-sub text-sm">抽取完成后显示。状态为「抽取中」时请稍候。</div>}
          </div>
        </aside>
      </div>
    </div>
  );
}
