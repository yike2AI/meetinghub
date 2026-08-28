import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Input, message } from "antd";
import { useEffect, useState } from "react";
import Markdown from "react-markdown";
import { useParams } from "react-router-dom";
import { api } from "../api";
import { Badge, PageHead } from "../ui";

export function ReportDetail() {
  const { id } = useParams();
  const rid = Number(id);
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["report", rid], queryFn: () => api.report(rid) });
  const [md, setMd] = useState("");
  const [edit, setEdit] = useState(false);
  useEffect(() => { if (data?.content_md) setMd(data.content_md); }, [data]);
  const save = useMutation({
    mutationFn: () => api.saveReport(rid, md),
    onSuccess: () => { message.success("已保存"); qc.invalidateQueries({ queryKey: ["report", rid] }); setEdit(false); },
  });
  return (
    <div>
      <PageHead
        title={`${data?.period_label || ""} 复盘报告`}
        extra={
          <div className="flex gap-2 items-center">
            <Badge status={data?.status || "draft"} />
            <button className="btn-ghost" onClick={() => setEdit(!edit)}>{edit ? "预览" : "编辑"}</button>
            <button className="btn-primary" onClick={() => save.mutate()}>保存</button>
          </div>
        }
      />
      <div className="card p-8">
        {edit ? (
          <Input.TextArea rows={28} value={md} onChange={(e) => setMd(e.target.value)} />
        ) : (
          <article className="prose max-w-none text-[15px] leading-relaxed">
            <Markdown>{md}</Markdown>
          </article>
        )}
      </div>
    </div>
  );
}
