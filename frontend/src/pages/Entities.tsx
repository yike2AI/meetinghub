import { useQuery } from "@tanstack/react-query";
import { Select } from "antd";
import { useState } from "react";
import { api } from "../api";
import { EntityRow, Empty, PageHead } from "../ui";

export function Entities() {
  const { data: spaces } = useQuery({ queryKey: ["spaces"], queryFn: api.spaces });
  const [type, setType] = useState<string>();
  const [spaceId, setSpaceId] = useState<number>();
  const qs = `?${type ? `type=${type}&` : ""}${spaceId ? `space_id=${spaceId}` : ""}`;
  const { data } = useQuery({ queryKey: ["entities", qs], queryFn: () => api.entities(qs) });
  return (
    <div>
      <PageHead kicker="Entities" title="实体库" desc="决策、承诺、风险三类资产。点击任意一条跳回原文。" extra={
        <div className="flex gap-3">
          <Select allowClear placeholder="类型" className="w-36" value={type} onChange={setType} options={[{ value: "decision", label: "决策" }, { value: "commitment", label: "承诺" }, { value: "risk", label: "风险" }]} />
          <Select allowClear placeholder="空间" className="w-52" value={spaceId} onChange={setSpaceId} options={(spaces || []).map((s: any) => ({ value: s.id, label: s.name }))} />
        </div>
      } />
      <div className="space-y-3">
        {(data || []).map((e: any) => <EntityRow key={e.id} e={e} />)}
        {(data || []).length === 0 && <Empty title="暂无实体" hint="先入库一场会议并完成抽取。完成后，决策 / 承诺 / 风险会出现在这里。" />}
      </div>
    </div>
  );
}
