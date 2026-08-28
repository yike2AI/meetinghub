import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import { fmtDate } from "../lib";
import { Badge, PageHead } from "../ui";

export function Workbench() {
  const { data } = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard, refetchInterval: 8000 });
  const stats = data?.stats || {};
  return (
    <div>
      <PageHead kicker="Workbench" title="工作台" desc="会议入库后，在这里确认实体、回看档案、发起复盘问答。" extra={<Link className="btn-primary" to="/import">导入会议</Link>} />
      <div className="grid grid-cols-3 gap-4">
        {[
          ["本库会议", stats.meetings ?? 0, "场"],
          ["待确认", stats.pending_confirmations ?? 0, "项"],
          ["结构化实体", stats.entities ?? 0, "条"],
        ].map(([k, v, u]) => (
          <div key={k as string} className="card p-6">
            <div className="text-text-sub text-[13px]">{k}</div>
            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-[40px] font-semibold text-brand leading-none">{v as number}</span>
              <span className="text-text-sub text-[13px]">{u as string}</span>
            </div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-6 mt-8">
        <section className="card p-6">
          <h2 className="text-[18px] font-semibold">待确认任务</h2>
          <div className="mt-4 space-y-2">
            {(data?.pending_tasks || []).length === 0 && (
              <div className="text-text-sub text-sm py-8 text-center leading-relaxed">暂无待确认任务。<br />导入真实会议并完成抽取后会出现在这里。</div>
            )}
            {(data?.pending_tasks || []).map((t: any) => (
              <Link key={t.meeting_id} to={`/meetings/${t.meeting_id}/confirm`} className="row-card !p-3">
                <div className="font-medium">{t.title}</div>
                <div className="text-[12px] text-text-sub mt-1">截止 {fmtDate(t.deadline_at)}</div>
              </Link>
            ))}
          </div>
        </section>
        <section className="card p-6">
          <h2 className="text-[18px] font-semibold">最近会议</h2>
          <div className="mt-4 space-y-2">
            {(data?.recent_meetings || []).length === 0 && (
              <div className="text-text-sub text-sm py-8 text-center leading-relaxed">还没有会议档案。<br />从空间页粘贴飞书妙记链接即可入库。</div>
            )}
            {(data?.recent_meetings || []).map((m: any) => (
              <Link key={m.id} to={`/meetings/${m.id}`} className="row-card !p-3 flex items-center justify-between">
                <div>
                  <div className="font-medium">{m.title}</div>
                  <div className="text-[12px] text-text-sub mt-1">{fmtDate(m.held_at)}</div>
                </div>
                <Badge status={m.status} />
              </Link>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
