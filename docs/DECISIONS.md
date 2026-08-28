# POC 决策日志

| 日期 | 决策 | 原因 |
| --- | --- | --- |
| 2026-08-13 | 中文全文检索用应用层 jieba 分词写入 `transcript_segment.search_vector`（`to_tsvector('simple', ...)`），不用 pg_jieba | Windows + 官方 pgvector 镜像安装 pg_jieba 成本高 |
| 2026-08-13 | Chat 走智谱 Anthropic 兼容端点；embedding-3 因账号 1113 余额不足，POC 用 jieba 哈希向量兜底 | paas/v4 的 glm-4-plus/glm-5.1/embedding 返回 1113；anthropic 端点 glm-5.1 可用 |
| 2026-08-13 | Agent 用 ModelGateway 的 OpenAI 兼容 tool-calling 循环，不嵌入 claude-agent-sdk 进程 | 工具契约与 02 文档一致；避免 SDK 与 GLM 端点的额外运行时耦合 |
| 2026-08-13 | 增加 `sync_run` 表记录最近同步状态 | 02 DDL 无此表，空间详情「立即同步」需要可展示状态 |
| 2026-08-13 | POC 启动时 `create_all` 建表，docker 仅执行 `CREATE EXTENSION vector` | 本机快速迭代；正式版再切 alembic |
| 2026-08-13 | 确认超时默认 5 分钟（`.env` `CONFIRM_TIMEOUT_MINUTES`） | POC 演示自动入库，正式值 2880 |
| 2026-08-13 | 档案固定三层：原文（逐字稿）→ AI 总结（优先飞书/钉钉平台产物；没有则本系统按「要点大纲 + 结论/待办」统一模板补写）→ 核心资产（decision/commitment/risk，跨会可检索）。不按分享会/讨论会分型 | 单场纪要平台已做；本系统差异化在跨会资产。分型增加标注成本且与平台产物重复 |
