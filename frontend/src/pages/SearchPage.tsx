import { Input } from "antd";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Empty, PageHead } from "../ui";

export function SearchPage() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<any[]>([]);
  const [searched, setSearched] = useState(false);
  return (
    <div>
      <PageHead kicker="Search" title="检索溯源" desc="全文 + 向量混合检索。结果一键跳到逐字稿原文。" />
      <Input.Search
        size="large"
        placeholder="关键词或语义，例如：渠道改革"
        enterButton="检索"
        onSearch={async (v) => {
          setHits(await api.search(v));
          setSearched(true);
        }}
        onChange={(e) => setQ(e.target.value)}
        value={q}
      />
      <div className="mt-6 space-y-3">
        {hits.map((h, i) => (
          <Link
            key={i}
            to={h.kind === "entity" ? `/meetings/${h.meeting_id}?seg=${h.anchor_segment_ids?.[0]}` : `/meetings/${h.meeting_id}?seg=${h.segment_id}`}
            className="row-card"
          >
            <div className="text-[12px] text-text-sub">{h.kind === "entity" ? "实体" : "逐字稿"} · {h.meeting_title || `会议 ${h.meeting_id}`}</div>
            <div className="mt-2 leading-relaxed">{h.snippet || h.payload?.conclusion || h.payload?.item || h.payload?.description}</div>
            <div className="text-brand text-sm mt-2">跳转原文 →</div>
          </Link>
        ))}
        {!searched && <Empty title="输入关键词开始检索" hint="可以搜逐字稿原文，也可以搜已抽取的决策 / 承诺 / 风险。" />}
        {searched && hits.length === 0 && <Empty title="没有命中" hint="换个词试试，或先入库会议再检索。" />}
      </div>
    </div>
  );
}
