import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import { fmtDate } from "../lib";
import { Badge, Empty, PageHead } from "../ui";

export function Reports() {
  const { data } = useQuery({ queryKey: ["reports"], queryFn: () => api.reports() });
  return (
    <div>
      <PageHead kicker="Reports" title="复盘报告" desc="确认完成后可在空间页生成初稿，这里查看与继续编辑。" />
      <div className="space-y-3">
        {(data || []).map((r: any) => (
          <Link key={r.id} to={`/reports/${r.id}`} className="row-card flex justify-between items-center">
            <div>
              <div className="font-medium">{r.period_label}</div>
              <div className="text-[12px] text-text-sub mt-1">{fmtDate(r.created_at)}</div>
            </div>
            <Badge status={r.status} />
          </Link>
        ))}
        {(data || []).length === 0 && <Empty title="还没有报告" hint="空间里至少有一场已确认的会议后，到空间详情页点击「生成本期报告」。" />}
      </div>
    </div>
  );
}
