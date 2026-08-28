import { useQuery } from "@tanstack/react-query";
import { DatePicker, Input, Select, Tabs, Upload, message } from "antd";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { Empty, PageHead } from "../ui";

export function ImportPage() {
  const nav = useNavigate();
  const { data: spaces } = useQuery({ queryKey: ["spaces"], queryFn: api.spaces });
  const [spaceId, setSpaceId] = useState<number>();
  const [title, setTitle] = useState("");
  const [held, setHeld] = useState("");
  const [people, setPeople] = useState("");
  const [paste, setPaste] = useState("");

  async function send(fd: FormData) {
    if (!spaceId) {
      message.warning("请先选择空间");
      return;
    }
    fd.set("space_id", String(spaceId));
    fd.set("title", title);
    fd.set("held_at", held);
    fd.set("participants", people);
    const r = await api.importMeeting(fd);
    message.success("已导入并进入抽取");
    if (r.meeting_id) nav(`/meetings/${r.meeting_id}`);
  }

  return (
    <div>
      <PageHead kicker="Import" title="导入会议" desc="支持 txt / srt / docx / pdf，或 zip+CSV 批量回灌。导入后自动进入抽取管道。" />
      {(spaces || []).length === 0 && (
        <Empty title="还没有空间，无法导入" hint="导入必须归属到一个空间。先创建空间再回来。" action={<button className="btn-primary" onClick={() => nav("/spaces/new")}>创建空间</button>} />
      )}
      <div className="card p-6 grid grid-cols-2 gap-4">
        <Select placeholder="选择空间" className="w-full" size="large" value={spaceId} onChange={setSpaceId} options={(spaces || []).map((s: any) => ({ value: s.id, label: s.name }))} />
        <Input placeholder="会议标题" size="large" value={title} onChange={(e) => setTitle(e.target.value)} />
        <DatePicker showTime className="w-full" size="large" onChange={(_, v) => setHeld(Array.isArray(v) ? String(v[0] || "") : v)} />
        <Input placeholder="参会人，逗号分隔" size="large" value={people} onChange={(e) => setPeople(e.target.value)} />
      </div>
      <Tabs
        className="mt-6"
        items={[
          {
            key: "one",
            label: "单文件 / 粘贴",
            children: (
              <div className="card p-6 space-y-4">
                <Upload.Dragger
                  beforeUpload={async (file) => {
                    const fd = new FormData();
                    fd.append("file", file);
                    await send(fd);
                    return false;
                  }}
                  showUploadList={false}
                >
                  <p className="text-[15px]">拖拽 txt / srt / docx / pdf 到这里</p>
                  <p className="text-text-sub text-[13px] mt-1">文件会永久归档，不会物理删除</p>
                </Upload.Dragger>
                <Input.TextArea rows={8} placeholder="或直接粘贴逐字稿" value={paste} onChange={(e) => setPaste(e.target.value)} />
                <button
                  className="btn-primary"
                  onClick={async () => {
                    const fd = new FormData();
                    fd.set("paste_text", paste);
                    await send(fd);
                  }}
                >
                  导入粘贴文本
                </button>
              </div>
            ),
          },
          {
            key: "batch",
            label: "批量 zip+CSV",
            children: (
              <div className="card p-6">
                <p className="text-sm text-text-sub mb-4">CSV 列：filename, title, held_at, space_id, participants。zip 内同时放会议文件。</p>
                <Upload.Dragger
                  accept=".zip"
                  beforeUpload={async (file) => {
                    if (!spaceId) {
                      message.warning("请先选择空间");
                      return false;
                    }
                    const fd = new FormData();
                    fd.append("file", file);
                    fd.set("space_id", String(spaceId));
                    await api.importMeeting(fd);
                    message.success("批量导入已提交");
                    return false;
                  }}
                  showUploadList={false}
                >
                  <p>上传 zip（内含会议文件 + 元数据 CSV）</p>
                </Upload.Dragger>
              </div>
            ),
          },
        ]}
      />
    </div>
  );
}
