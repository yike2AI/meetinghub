import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { fmtDate } from "../lib";
import { Empty, PageHead } from "../ui";

export function AskEntry() {
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const { data: spaces } = useQuery({ queryKey: ["spaces"], queryFn: api.spaces });
  const { data: sessions } = useQuery({ queryKey: ["sessions"], queryFn: api.sessions });
  useEffect(() => {
    const spaceId = sp.get("spaceId");
    const q = sp.get("q");
    if (!spaceId) return;
    void api.createSession({ space_id: Number(spaceId) }).then((s) => {
      nav(`/ask/${s.id}${q ? `?q=${encodeURIComponent(q)}` : ""}`, { replace: true });
    });
  }, [sp, nav]);

  return (
    <div>
      <PageHead kicker="Ask" title="复盘问答" desc="先选空间，再提问。每个结论必须带原文引用，查不到就如实说未找到。" />
      <div className="grid grid-cols-2 gap-4">
        {(spaces || []).map((s: any) => (
          <button
            key={s.id}
            className="card-lift p-6 text-left"
            onClick={async () => {
              const sess = await api.createSession({ space_id: s.id });
              nav(`/ask/${sess.id}`);
            }}
          >
            <div className="text-[20px] font-semibold">{s.name}</div>
            <div className="text-sm text-text-sub mt-2">{s.meeting_count} 场会议 · 点击开始会话</div>
          </button>
        ))}
      </div>
      {(spaces || []).length === 0 && (
        <Empty title="还没有可提问的空间" hint="先创建空间并入库至少一场会议，再回来选范围提问。" action={<button className="btn-primary" onClick={() => nav("/spaces/new")}>创建空间</button>} />
      )}
      <h2 className="text-[18px] font-semibold mt-10 mb-3">最近会话</h2>
      <div className="space-y-2">
        {(sessions || []).length === 0 && <Empty title="还没有会话" hint="选一个空间后开始提问。每个结论都会带原文引用。" />}
        {(sessions || []).map((s: any) => (
          <button key={s.id} className="row-card w-full text-left" onClick={() => nav(`/ask/${s.id}`)}>
            <div className="font-medium">{s.title || `会话 #${s.id}`}</div>
            <div className="text-[12px] text-text-sub mt-1">{fmtDate(s.created_at)}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
