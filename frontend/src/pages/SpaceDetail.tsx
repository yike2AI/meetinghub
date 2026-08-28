import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Input, Tabs, message } from "antd";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { fmtDate } from "../lib";
import { Badge, EntityRow, Empty, PageHead } from "../ui";

export function SpaceDetail() {
  const { id } = useParams();
  const sid = Number(id);
  const nav = useNavigate();
  const qc = useQueryClient();
  const { data: space } = useQuery({ queryKey: ["space", sid], queryFn: () => api.space(sid), refetchInterval: 10000 });
  const { data: meetings } = useQuery({ queryKey: ["smeet", sid], queryFn: () => api.spaceMeetings(sid), refetchInterval: 8000 });
  const { data: entities } = useQuery({ queryKey: ["ents", sid], queryFn: () => api.entities(`?space_id=${sid}`) });
  const { data: topics } = useQuery({ queryKey: ["topics", sid], queryFn: () => api.topics(sid) });
  const { data: reports } = useQuery({ queryKey: ["reports", sid], queryFn: () => api.reports(sid) });
  const [link, setLink] = useState("");
  const [cid, setCid] = useState("");
  const syncMut = useMutation({
    mutationFn: () => api.syncSpace(sid),
    onSuccess: (d) => {
      message.success(`同步完成，新入库 ${d.pulled || 0} 场`);
      qc.invalidateQueries();
    },
    onError: (e: any) => message.error(e.message),
  });

  const insights = space?.insights || {};
  const cards = [
    { title: "悬空承诺", n: insights.hanging_commitments ?? 0, q: insights.prompts?.hanging, hint: "近 45 天无后续提及" },
    { title: "议而不决", n: insights.stalled_topics ?? 0, q: insights.prompts?.stalled, hint: "讨论多次仍无决策" },
    { title: "活跃风险", n: insights.active_risks ?? 0, q: insights.prompts?.risks, hint: "近 60 天仍被提及" },
  ];

  return (
    <div>
      <PageHead
        kicker="Space"
        title={space?.name || "空间"}
        desc={`最近同步：${(space?.sync_runs || [])[0]?.message || "尚未同步"}`}
        extra={
          <button className="btn-primary" onClick={() => syncMut.mutate()} disabled={syncMut.isPending}>
            {syncMut.isPending ? "同步中…" : "立即同步"}
          </button>
        }
      />
      <div className="grid grid-cols-3 gap-4">
        {cards.map((c) => (
          <button key={c.title} className="card-lift p-5 text-left" onClick={() => nav(`/ask?spaceId=${sid}&q=${encodeURIComponent(c.q || "")}`)}>
            <div className="text-text-sub text-[13px]">{c.title}</div>
            <div className="text-[32px] font-semibold text-brand mt-1">{c.n}</div>
            <div className="text-[12px] text-text-sub mt-1">{c.hint}</div>
            <div className="text-[12px] text-brand mt-3">点击进入预填问答 →</div>
          </button>
        ))}
      </div>
      {!space?.dingtalk_configured && <div className="mt-4 text-[13px] text-warn">钉钉通道待配置，可用下方飞书链接或人工导入。</div>}
      <div className="card p-5 mt-6 grid grid-cols-2 gap-3">
        <div className="flex gap-2">
          <Input value={link} onChange={(e) => setLink(e.target.value)} placeholder="粘贴飞书妙记链接" />
          <button
            className="btn-primary shrink-0"
            onClick={async () => {
              try {
                await api.feishuLink({ url: link, space_id: sid });
                message.success("已触发拉取，正在抽取");
                qc.invalidateQueries();
              } catch (e: any) {
                message.error(e.message || "飞书拉取失败");
              }
            }}
          >
            拉取妙记
          </button>
        </div>
        <div className="flex gap-2">
          <Input value={cid} onChange={(e) => setCid(e.target.value)} placeholder="粘贴钉钉听记链接或 conferenceId" />
          <button
            className="btn-ghost shrink-0"
            onClick={async () => {
              try {
                const r = await api.dingtalkPull({ conference_id: cid, space_id: sid });
                message.success(r.empty ? "无数据" : "已触发拉取");
                qc.invalidateQueries();
              } catch (e: any) {
                message.error(e.message || "钉钉拉取失败");
              }
            }}
          >
            拉取听记
          </button>
        </div>
      </div>
      <Tabs
        className="mt-6"
        items={[
          {
            key: "m",
            label: `会议 ${meetings?.length || 0}`,
            children: (
              <div className="space-y-2">
                {(meetings || []).length === 0 && <Empty title="这个空间还没有会议" hint="上方粘贴飞书妙记链接并拉取，或到导入页上传逐字稿。" />}
                {(meetings || []).map((m: any) => (
                  <Link key={m.id} to={`/meetings/${m.id}`} className="row-card flex items-center justify-between">
                    <div>
                      <div className="font-medium">{m.title}</div>
                      <div className="text-[12px] text-text-sub mt-1">{fmtDate(m.held_at)}</div>
                    </div>
                    <Badge status={m.status} />
                  </Link>
                ))}
              </div>
            ),
          },
          {
            key: "e",
            label: "实体库",
            children: (
              <div className="space-y-2">
                {(entities || []).length === 0 && <Empty title="暂无实体" hint="会议抽取完成后，决策 / 承诺 / 风险会出现在这里。" />}
                {(entities || []).map((e: any) => <EntityRow key={e.id} e={e} />)}
              </div>
            ),
          },
          {
            key: "t",
            label: "议题",
            children: (
              <div className="space-y-2">
                {(topics || []).length === 0 && <Empty title="暂无议题" hint="抽取管道会把实体聚类成议题。完成抽取后可看时间线。" />}
                {(topics || []).map((t: any) => (
                  <Link key={t.id} to={`/topics/${t.id}`} className="row-card">
                    <span className="badge bg-[#F5F3FF] text-topic">{t.name}</span>
                    <div className="text-sm text-text-sub mt-2">{t.summary}</div>
                  </Link>
                ))}
              </div>
            ),
          },
          {
            key: "r",
            label: "报告",
            children: (
              <div className="space-y-2">
                <button className="btn-primary mb-3" onClick={async () => { const r = await api.generateReport({ space_id: sid }); nav(`/reports/${r.id}`); }}>生成本期报告</button>
                {(reports || []).length === 0 && <Empty title="还没有报告" hint="先确认实体，再点「生成本期报告」。" />}
                {(reports || []).map((r: any) => (
                  <Link key={r.id} to={`/reports/${r.id}`} className="row-card flex justify-between">
                    <span>{r.period_label}</span>
                    <Badge status={r.status} />
                  </Link>
                ))}
              </div>
            ),
          },
          {
            key: "a",
            label: "问答",
            children: <button className="btn-primary" onClick={() => nav(`/ask?spaceId=${sid}`)}>进入复盘问答</button>,
          },
        ]}
      />
    </div>
  );
}
