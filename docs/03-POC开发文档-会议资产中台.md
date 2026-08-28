# POC 开发文档：会议资产中台（全链路验证版）

- 文档版本：v1.0
- 日期：2026-08-12
- 用途：POC 阶段的开发执行文档，交付给 AI 开发者直接实现。本文是《02-开发文档》的**蒸馏版**：功能规格细节（prompt、schema、交互）沿用 02 文档对应章节，**凡本文与 02 冲突处，POC 阶段以本文为准**。
- 目标：**跑通全链路**——钉钉/飞书自动拉取 + 人工导入 → 抽取 → 确认 → 资产库/时间线 → 复盘问答/研判 → 复盘报告。**不做任何鉴权与权限控制**。

---

## 0. POC 执行原则

1. **主线功能一个不少，管控能力全部剥离**：无登录、无角色、无空间成员过滤、无审计——系统打开即用，单用户模式。
2. **数据模型不打折**：建表沿用 02 文档第 7 章全量 DDL（含 space_member、audit_log 等权限相关表），POC 只是**不实现**相关逻辑。转正式版时加逻辑不动表。
3. **两条铁律不因 POC 妥协**：原始材料永久入库；实体锚点强校验（宁可漏、不可编）。
4. LLM 调用一律经 ModelGateway；前端样式遵循根目录 `DESIGN_GUIDE.md`。
5. 未覆盖的决策点选最简实现，记录到 `docs/DECISIONS.md`。

## 1. 范围

### 1.1 保留（全部实现）

| 环节 | POC 实现 | 相对 02 的简化 |
| --- | --- | --- |
| 空间管理 | 创建/编辑空间 + **同步配置向导**（见 5.1） | 无成员/密级/确认人角色语义（确认人仅作通知目标） |
| 钉钉自动拉取 | 听记文本 API 轮询 + 手动粘贴 conferenceId 触发 | 不做公网事件回调 |
| 飞书自动拉取 | **lark-cli 个人身份子进程方案**（见 5.3）：定时查询新妙记 + 自动导出逐字稿；支持粘贴妙记链接触发 | 不建自建应用 OAuth（正式版再切） |
| 人工导入 | 单文件（txt/srt/docx/pdf）+ 批量 zip 回灌 | 无 |
| 归一化与档案 | 统一落库；档案页三层：**原文**（逐字稿）/ **AI 总结**（平台纪要，无则模型补写）/ **核心资产**（决策·承诺·风险，带锚点） | 无 |
| AI 抽取管道 | 先落/补 AI 总结（§5.5），再 ModelGateway Pass1/Pass2 + 锚点校验 + 议题聚类（规格=02 §11.3） | 不自写替代平台的单场纪要；golden set 正式评估延后 |
| 确认流 | 确认页（确认/修改/删除/补录）+ 状态机 + 超时自动入库 + 修订留痕 | 任何人可确认（无角色校验）；超时时长可配置（演示用分钟级） |
| 资产库 | 实体库+筛选、混合检索（全文+向量）、溯源跳转、议题时间线 | 议题合并/拆分不做 |
| 提及追踪+洞察卡 | entity_mention 预计算 + 空间三张洞察卡（规格=02 §11.9.4/11.9.5） | 无 |
| 复盘问答 | Agent SDK 底座 + 9 工具 + SSE 流式 + 引用卡 + 预设 chips（规格=02 §11.5/11.9） | 无（POC 演示核心） |
| 复盘报告 | 生成 + 查看 + 在线编辑（模板=02 §M8） | 定稿流转、docx/pdf 导出不做 |
| 通知 | 钉钉**群机器人 webhook**：确认任务、报告就绪、拉取失败 | 不用企业工作通知 |

### 1.2 不做

登录/免登/JWT、角色与空间成员过滤、审计日志逻辑、腾讯会议、二次复盘 Agent、报告导出、议题管理、正式评估体系、CI/备份。

## 2. 环境与凭据现状（已盘点，2026-08-12）

| 项 | 状态 | 说明 |
| --- | --- | --- |
| GLM（智谱）API Key | ✅ 已有 | 位于 `C:\Users\94011\.claude\settings.json` → `ANTHROPIC_AUTH_TOKEN`，配套 Anthropic 兼容端点 `https://open.bigmodel.cn/api/anthropic`。**开发时复制到本项目 `.env` 的 `GLM_API_KEY`，不要在代码/文档中硬编码** |
| DeepSeek API Key | ❌ 待补 | `.env` 留占位 `DEEPSEEK_API_KEY=`；到位后按 §6.1 启用对比 |
| 钉钉群机器人 | ✅ 已有 | 同文件 `DINGTALK_WEBHOOK` + `DINGTALK_SECRET`（加签），复制到 `.env` |
| 钉钉企业应用凭据 | ⏳ 等 IT | 需 appKey/appSecret + `VideoConference.Conference.Read` 权限；到位前钉钉通道自动跳过，人工导入顶上 |
| 飞书 lark-cli | ⚠️ 需重登录 | 本机已配置（app `cli_a979b39336fb5bdb`，用户"亦客"），个人 token 已过期。**前置动作：运行 `lark-cli auth login` 完成个人授权**（bot 身份已可用，但妙记列表查询需要 user 身份） |

`.env` 模板（随工程提交 `.env.example`，真实值不入库）：

```env
GLM_API_KEY=            # 从 ~/.claude/settings.json 的 ANTHROPIC_AUTH_TOKEN 复制
DEEPSEEK_API_KEY=       # 待补，可留空
DINGTALK_APP_KEY=       # 等 IT 提供
DINGTALK_APP_SECRET=    # 等 IT 提供
DINGTALK_WEBHOOK=       # 从 ~/.claude/settings.json 复制
DINGTALK_SECRET=        # 同上（加签密钥）
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/meetinghub
REDIS_URL=redis://localhost:6379/0
CONFIRM_TIMEOUT_MINUTES=2880   # 确认超时，演示时可改为 5
```

## 3. 架构与技术栈（POC 简化）

架构同 02 §3，删去"鉴权/权限过滤"职责；技术栈同 02 §4（FastAPI + SQLAlchemy + arq + Postgres16/pgvector + React/Vite/Tailwind + antd）。部署：本机 docker-compose（postgres + redis），api/worker/前端直接本地跑即可，不强制容器化。

中文全文检索：优先 pg_jieba；Windows/容器安装困难时降级方案——分词在应用层做（jieba 库）存 tsvector，或先仅用向量检索+ILIKE，记录到 DECISIONS.md。

## 4. 数据模型

沿用 02 文档第 7 章 DDL **全量建表**（alembic 迁移）。POC 行为差异：

- `app_user`：启动时 seed 一个默认用户（"POC 管理员"），所有操作归属该用户；
- `space_member`/`audit_log`：建表，不写逻辑；
- `space.match_rules` 扩展一种规则类型（飞书同步用）：

```json
{"type": "feishu_owner_sync", "keyword": "月度战略会", "since": "2026-01-01"}
```

含义：定时用个人身份查询妙记列表，标题含 keyword（可为空=全部）且时间 ≥ since 的新妙记，自动拉取归入本空间。

## 5. 数据接入实现

### 5.1 空间创建向导（同步配置入口）

创建空间三步：① 名称；② 同步配置（可多选：钉钉周期会议 conferenceId 列表 / 钉钉标题关键词 / 飞书 feishu_owner_sync 规则）；③ 确认人（下拉选用户，POC 仅作通知署名）。保存后立即触发一次同步，此后每 15 分钟轮询。空间详情页提供"立即同步"按钮与最近同步状态。

### 5.2 钉钉通道（DingTalkAdapter）

- 凭据到位后启用；未配置 `DINGTALK_APP_KEY` 时通道自动禁用并在 UI 标注"待配置"。
- 拉取：`GET /v1.0/conference/videoConferences/{conferenceId}/cloudRecords/getTexts`（分页 nextToken），组装 RawMeeting（契约=02 §M3）。
- 触发：空间配置的 conferenceId 轮询（15 分钟）+ 档案页"粘贴 conferenceId 拉取"。
- 无录制/无文本：记录"无数据"状态，不报错。

### 5.3 飞书通道（FeishuAdapter，lark-cli 子进程方案）

POC 用本机 lark-cli 的**个人身份**完成自动同步，零新增审批：

1. **前置**（人工，一次性）：`lark-cli auth login` 完成个人授权；
2. **发现**：定时任务（15 分钟）以 user 身份调用 lark-cli 妙记列表查询（按所有者=本人 + 时间范围，具体命令以 `lark-cli minutes --help` 与本机 lark-minutes skill 文档为准），比对 `meeting.source_ref` 去重得到新妙记 token；
3. **导出**：`lark-cli vc +notes --minute-tokens <token> --output-dir <tmp> --format json` 拉逐字稿（cwd 必须为仓库根，`--output-dir` 必须是相对路径）。另调 OpenAPI `GET /open-apis/minutes/v1/minutes/{token}/artifacts` 取 `summary` / `minute_todos` / `minute_chapters`，写入 `platform_artifact`。该妙记若平台未生成总结，抽取阶段按 §5.5 补写。
4. **手动触发**：前端粘贴妙记链接（正则提取 24 位 minute_token）→ 直接执行步骤 3；
5. **实现要点**：子进程调用封装（超时 120s、stderr 捕获、JSON 解析）；token 过期时 UI 明确提示"运行 lark-cli auth login 重新授权"；该 Adapter 输出与其他通道相同的 RawMeeting 契约，正式版切换为自建应用原生 API 时仅替换本模块内部实现。

### 5.4 人工导入与批量回灌

同 02 §M3.3/§F1.3/F1.4：单文件（txt/srt/docx/pdf/粘贴文本）+ 元数据表单；zip+CSV 批量模式。**历史战略会材料（约几十场）在 POC 期间完成回灌**——它是演示纵深与调优主粮。导入通道没有平台纪要，抽取前由本系统按 §5.5 补写 AI 总结。

### 5.5 档案三层：原文 / AI 总结 / 核心资产

单场「写纪要」不是本系统的差异化能力（飞书妙记、钉钉听记已具备）。POC 档案页固定三层，确认流只作用在第三层：

| 层 | 名称 | 来源 | 是否进确认 |
| --- | --- | --- | --- |
| 1 | **原文** | 逐字稿 segments（发言人+时间戳），永久留存 | 否 |
| 2 | **AI 总结** | **优先**平台产物：飞书 `artifacts.summary/todos/chapters`；钉钉凭据到位后接智能纪要。平台没有（人工导入、或接口未返回）时，用 ModelGateway 按统一模板补写，kind=`generated_summary`，UI 标注「本系统补写」 | 否（展示用） |
| 3 | **核心资产** | Pass1/Pass2 抽取 decision / commitment / risk，锚点必须落在原文；平台总结与补写总结仅作 Pass2 召回参考，不能替代原文证据 | 是 |

补写模板（不区分分享会/讨论会）：

```text
要点大纲：3–8 条（分享会自然体现观点，讨论会自然体现议题推进）
结论：会上较明确的定论，可空
待办：事项 + 责任人（原文明确才填），可空
```

实现要点：

- 飞书 Adapter 必须把 JSON 里的 summary/todos/chapters **拆条入库**，禁止把整段 CLI 输出当一份 summary；
- 钉钉 Adapter 在 `DINGTALK_APP_KEY` 到位前 artifacts 可为空，抽取阶段走补写；到位后补智能纪要接口，契约仍是上述三种 kind；
- 档案页左栏 Tab「原文 | AI 总结」，右栏「核心资产」点击跳原文高亮；AI 总结区展示来源徽章（飞书妙记 / 钉钉听记 / 本系统补写）；
- 重跑抽取时：平台产物保留；`generated_summary` 可覆盖重生。

## 6. AI 配置

### 6.1 models.yaml（POC 版）

单一 GLM key 跑通全链路；DeepSeek 到位后仅改此文件做对比：

```yaml
# 结构化调用走智谱 OpenAI 兼容端点 https://open.bigmodel.cn/api/paas/v4
extract_pass1:  {provider: zhipu, model: glm-5.2, api_key_env: GLM_API_KEY}
extract_pass2:  {provider: zhipu, model: glm-5.2, api_key_env: GLM_API_KEY}
meeting_summary: {provider: zhipu, model: glm-5.2, api_key_env: GLM_API_KEY}
topic_naming:   {provider: zhipu, model: glm-5.2, api_key_env: GLM_API_KEY}
report_compare: {provider: zhipu, model: glm-5.2, api_key_env: GLM_API_KEY}
mention_judge:  {provider: zhipu, model: glm-5.2, api_key_env: GLM_API_KEY}
embedding:      {provider: zhipu, model: embedding-3, dimensions: 1024, api_key_env: GLM_API_KEY}
# DeepSeek 对比配置（key 到位后取消注释逐项切换）：
# extract_pass1: {provider: deepseek, model: deepseek-chat, api_key_env: DEEPSEEK_API_KEY}
# 注意：DeepSeek 无 embedding 接口，embedding 保持 GLM 或换本地 bge-m3
```

模型名以智谱当期实际可用为准（glm-5.2 不可用则降 glm-5.1，记录 DECISIONS.md）。

### 6.2 问答 Agent（Claude Agent SDK on GLM）

```env
# Agent 服务进程环境变量（与 Claude Code 同款配置，已验证可用）
ANTHROPIC_BASE_URL=https://open.bigmodel.cn/api/anthropic
ANTHROPIC_AUTH_TOKEN=${GLM_API_KEY}
ANTHROPIC_MODEL=glm-5.2   # 不可用则 glm-5.1
```

- 工具集 9 个、PreToolUse hook 结构、system prompt、SSE 事件流、引用校验、chips：全部按 02 §11.5/§11.9 实现；
- POC 差异：hook 中的越权校验退化为"仅校验资源存在性"（无权限语义）；单轮 max_turns=10、每日限额逻辑不做；
- DeepSeek 备选：`ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`。

### 6.3 抽取质量（POC 标准）

不建 golden set，改为：每导入一批会议后，人工抽查 2 场的实体清单，记录漏抽/错抽到 `docs/QUALITY_LOG.md`；锚点校验硬性拦截照常（02 §11.3/11.4 不打折）。

## 7. 前端页面（POC 集）

按 02 §10 页面清单实现以下子集，样式 token 遵循 DESIGN_GUIDE.md：

| 路由 | 说明 |
| --- | --- |
| / | 工作台：统计卡 + 待确认任务 + 最近会议 |
| /spaces、/spaces/:id | 空间列表；空间详情（洞察卡行 + Tab：会议/实体库/议题/报告/问答）+ 同步配置与"立即同步" |
| /meetings/:id | 会议档案：左栏 Tab「原文 / AI 总结」；右栏核心资产（决策·承诺·风险），点击跳原文高亮 |
| /meetings/:id/confirm | 确认页（进度条 + 一键全部确认 + 倒计时） |
| /entities、/search | 实体库筛选；混合检索+溯源跳转 |
| /topics/:id | 议题时间线 |
| /reports、/reports/:id | 报告列表；报告查看/在线编辑 |
| /ask、/ask/:sessionId | 问答入口（选空间）；会话页（chips + SSE + 引用卡 + 过程可见） |
| /import | 导入页（单文件 + 批量 Tab） |

不做：/login、/admin、移动端适配（桌面浏览器优先）。

## 8. 开发顺序（D1~D7）

| 天 | 任务 | 当日验收 |
| --- | --- | --- |
| D1 | 工程骨架 + 全量 DDL + ModelGateway（GLM 打通）+ seed 用户 | 空应用可跑，GLM 调用与 embedding 冒烟通过 |
| D2 | 人工导入（单+批量）+ 归一化 + 空间创建向导 + 会议列表/档案页 | 导入真实 srt，档案页逐字稿完整可读 |
| D3 | 抽取管道（Pass1/Pass2/锚点校验/议题聚类） | 对 2 场真实会议出实体，锚点 100% 可跳转，人工抽查记录 |
| D4 | 确认流（确认页/状态机/超时/留痕）+ webhook 通知；entity_mention 预计算 + 洞察卡 | 演示级超时（5 分钟）自动入库正确；洞察卡出真实信号 |
| D5 | 实体库 + 混合检索 + 溯源 + 议题时间线；批量回灌全部历史材料 | 时间线跨 ≥3 场会议；检索命中并跳原文 |
| D6 | 问答 Agent（SDK 底座 + 工具 + SSE + 前端会话页 + chips + 引用卡） | 事实/溯因/研判三层问题各答对一例，引用可点击 |
| D7 | 复盘报告（生成+编辑）+ 钉钉/飞书自动同步联调（凭据到位的通道）+ 全链路串演 | POC 验收清单（§9）全过 |

钉钉凭据/lark-cli 登录未就绪不阻塞对应天次，其余任务照常，通道联调顺延。

## 9. POC 验收清单（演示脚本）

- [ ] 创建"战略会空间"并配置飞书同步规则，个人账号下新妙记 15 分钟内自动入库（或手动"立即同步"成功）
- [ ] 钉钉粘贴 conferenceId 拉取成功（凭据到位为前提）
- [ ] 批量回灌历史战略会材料完成，时间线具备多月纵深
- [ ] 任选一场会议：档案三层完整（原文 / AI 总结带来源徽章 / 核心资产带锚点），点击资产跳原文高亮
- [ ] 确认页修改一条实体并确认；另一场会议演示超时自动入库且带"AI 自动入库"标记
- [ ] 空间洞察卡显示真实信号，点击进入预填问答
- [ ] 问答演示三问：「上次会定了什么」（事实）、「XX 决策当时的依据」（溯因）、「哪些承诺后来没下文」（研判），每答附可点击引用
- [ ] 生成本期复盘报告初稿，在线编辑保存
- [ ] 全程无登录、无权限拦截（POC 预期行为）

## 10. 转正式版切换点（POC 完成后逐项加回）

登录与免登（02 §M1）→ 空间成员与行级过滤（02 §M2/§9）→ 审计逻辑（02 §M10）→ 飞书切自建应用原生 API → 钉钉事件回调 → 报告定稿/导出 → golden set 评估（02 §11.8）→ 二次复盘 Agent。
