import { useMutation, useQuery } from "@tanstack/react-query";
import { Input, Select, Switch, message } from "antd";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { PageHead } from "../ui";

export function SpaceCreate() {
  const nav = useNavigate();
  const { data: users } = useQuery({ queryKey: ["users"], queryFn: api.users });
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: api.me });
  const [step, setStep] = useState(0);
  const [name, setName] = useState("战略会空间");
  const [conferenceIds, setConferenceIds] = useState("");
  const [titleKw, setTitleKw] = useState("");
  const [feishuOn, setFeishuOn] = useState(true);
  const [feishuKw, setFeishuKw] = useState("");
  const [feishuSince, setFeishuSince] = useState("2026-01-01");
  const [confirmer, setConfirmer] = useState<number>();
  const dingtalkOk = me?.dingtalk_configured;

  const mut = useMutation({
    mutationFn: api.createSpace,
    onSuccess: (d) => {
      message.success("空间已创建，正在同步");
      nav(`/spaces/${d.id}`);
    },
    onError: (e: any) => message.error(e.message),
  });

  function submit() {
    const rules: any[] = [];
    if (conferenceIds.trim()) {
      conferenceIds.split(",").map((x) => x.trim()).filter(Boolean).forEach((id) =>
        rules.push({ type: "recurring_meeting_id", platform: "dingtalk", value: id })
      );
    }
    if (titleKw.trim()) rules.push({ type: "title_keyword", value: titleKw.trim() });
    if (feishuOn) rules.push({ type: "feishu_owner_sync", keyword: feishuKw, since: feishuSince || "2026-01-01" });
    mut.mutate({ name, confirmer_user_id: confirmer, match_rules: rules, report_enabled: true, security_level: "exec" });
  }

  const steps = ["名称", "同步配置", "确认人"];
  return (
    <div className="max-w-[720px]">
      <PageHead kicker="New space" title="创建空间" desc="三步完成：命名、配置自动拉取、指定确认人。保存后立即同步一次。" />
      <div className="flex gap-2 mb-8">
        {steps.map((s, i) => (
          <button key={s} onClick={() => setStep(i)} className={`flex-1 rounded-[12px] py-2.5 text-[13px] font-medium border ${i === step ? "text-white border-transparent bg-gradient-to-r from-[#165DFF] to-[#044AE9]" : "bg-white border-line text-text-sub"}`}>
            {i + 1} · {s}
          </button>
        ))}
      </div>
      <div className="card p-8">
        {step === 0 && (
          <div>
            <label className="text-[13px] font-medium">空间名称</label>
            <Input className="mt-2" size="large" value={name} onChange={(e) => setName(e.target.value)} placeholder="战略会空间" />
            <p className="text-[12px] text-text-sub mt-3">例如「战略会空间」「华东渠道项目会」。POC 不做密级隔离。</p>
          </div>
        )}
        {step === 1 && (
          <div className="space-y-5">
            <p className="text-[13px] text-text-sub">可多选。凭据未就绪的通道会自动跳过，人工导入始终可用。</p>
            <div>
              <label className="text-[13px] font-medium">钉钉周期会议 conferenceId（逗号分隔）</label>
              <Input className="mt-2" value={conferenceIds} onChange={(e) => setConferenceIds(e.target.value)} disabled={!dingtalkOk} placeholder={dingtalkOk ? "粘贴 conferenceId" : "钉钉企业凭据待配置"} />
            </div>
            <div>
              <label className="text-[13px] font-medium">钉钉标题关键词</label>
              <Input className="mt-2" value={titleKw} onChange={(e) => setTitleKw(e.target.value)} disabled={!dingtalkOk} placeholder="月度战略会" />
            </div>
            <div className="flex items-center justify-between py-2">
              <div>
                <div className="text-[13px] font-medium">飞书：同步我拥有的妙记</div>
                <div className="text-[12px] text-text-sub mt-1">使用本机已登录的 lark-cli 个人身份，每 15 分钟轮询。</div>
              </div>
              <Switch checked={feishuOn} onChange={setFeishuOn} />
            </div>
            {feishuOn && (
              <>
                <div>
                  <label className="text-[13px] font-medium">标题关键词（可空 = 全部）</label>
                  <Input className="mt-2" value={feishuKw} onChange={(e) => setFeishuKw(e.target.value)} />
                </div>
                <div>
                  <label className="text-[13px] font-medium">起始日期</label>
                  <Input className="mt-2" value={feishuSince} onChange={(e) => setFeishuSince(e.target.value)} placeholder="2026-01-01" />
                </div>
              </>
            )}
          </div>
        )}
        {step === 2 && (
          <div>
            <label className="text-[13px] font-medium">确认人</label>
            <Select
              className="w-full mt-2"
              size="large"
              placeholder="选择确认人（POC 仅作通知署名）"
              value={confirmer}
              onChange={setConfirmer}
              options={(users || []).map((u: any) => ({ value: u.id, label: u.name }))}
            />
            <p className="text-[12px] text-text-sub mt-3">任何人都可以确认。超时未处理将自动入库并永久标记。</p>
          </div>
        )}
        <div className="flex justify-between mt-8">
          <button className="btn-ghost" onClick={() => (step === 0 ? nav("/spaces") : setStep(step - 1))}>{step === 0 ? "取消" : "上一步"}</button>
          {step < 2 ? (
            <button className="btn-primary" onClick={() => setStep(step + 1)} disabled={step === 0 && !name.trim()}>下一步</button>
          ) : (
            <button className="btn-primary" onClick={submit} disabled={mut.isPending}>{mut.isPending ? "创建中…" : "创建并立即同步"}</button>
          )}
        </div>
      </div>
    </div>
  );
}
