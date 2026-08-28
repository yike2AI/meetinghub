import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { entityTitle, fmtDate } from "../lib";
import { Badge, Empty, PageHead } from "../ui";

export function TopicPage() {
  const { id } = useParams();
  const { data } = useQuery({ queryKey: ["tl", id], queryFn: () => api.timeline(Number(id)) });
  const nodes = data?.nodes || [];
  return (
    <div className="max-w-[760px] mx-auto">
      <PageHead
        title={data?.topic?.name || "议题"}
        desc={data?.topic?.summary || "跨会议讨论演变"}
        extra={<Link className="btn-ghost" to={`/ask?q=${encodeURIComponent((data?.topic?.name || "") + " 这件事的来龙去脉？")}`}>就此议题提问</Link>}
      />
      {nodes.length === 0 ? (
        <Empty title="这条议题还没有时间线" hint="至少需要一场已抽取会议挂到该议题上。" />
      ) : (
        <div className="relative pl-8">
          <div className="absolute left-2 top-0 bottom-0 w-px bg-line" />
          {nodes.map((n: any) => (
            <div key={n.meeting.id} className="mb-8 relative">
              <div className="absolute -left-[23px] top-5 w-3 h-3 rounded-full bg-brand" />
              <div className="card p-5">
                <Link to={`/meetings/${n.meeting.id}`} className="font-semibold hover:text-brand">
                  {fmtDate(n.meeting.held_at).slice(0, 10)} · {n.meeting.title}
                </Link>
                <div className="mt-3 space-y-2">
                  {n.entities.map((e: any) => (
                    <Link key={e.id} to={`/meetings/${n.meeting.id}?seg=${e.anchor_segment_ids?.[0]}`} className="block text-sm">
                      <Badge status={e.type} /> {entityTitle(e)}
                    </Link>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
