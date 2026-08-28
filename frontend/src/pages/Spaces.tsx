import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Empty, PageHead } from "../ui";

export function Spaces() {
  const { data: spaces } = useQuery({ queryKey: ["spaces"], queryFn: api.spaces });
  return (
    <div>
      <PageHead kicker="Spaces" title="空间" desc="一个空间对应一类会议资产。创建时配置钉钉/飞书同步规则。" extra={<Link className="btn-primary" to="/spaces/new">创建空间</Link>} />
      <div className="grid grid-cols-2 gap-4">
        {(spaces || []).map((s: any) => (
          <Link key={s.id} to={`/spaces/${s.id}`} className="card-lift p-6 block">
            <div className="flex items-center justify-between">
              <div className="text-[20px] font-semibold">{s.name}</div>
              <span className="badge bg-[#F0F5FF] text-brand">{s.security_level === "exec" ? "高管" : "项目"}</span>
            </div>
            <div className="text-text-sub text-sm mt-3">本库 {s.meeting_count} 场会议</div>
            {!s.dingtalk_configured && <div className="text-[12px] text-warn mt-2">钉钉通道待配置，可用人工导入或飞书同步。</div>}
          </Link>
        ))}
        {(spaces || []).length === 0 && (
          <div className="col-span-2">
            <Empty title="还没有空间" hint="先创建一个空间，再同步飞书妙记或导入逐字稿。" action={<Link className="btn-primary" to="/spaces/new">创建空间</Link>} />
          </div>
        )}
      </div>
    </div>
  );
}
