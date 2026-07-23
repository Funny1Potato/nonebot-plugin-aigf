# CHANGELOG

## AI-group-friend（基于 nonebot-plugin-nyaturingtest 重构）

### 架构变更

- **移除 HippoRAG**：删除基于知识图谱的长期记忆检索系统（`hippo_mem.py`、`siliconflow_embeddings.py`），改为 LLM 自主管理记忆
- **移除情绪系统**：删除 VAD 三维情感模型（`emotion.py`、`impression.py`、`profile.py`）
- **移除三阶段对话流水线**：原版为"检索→反馈→对话"三阶段，每阶段各调一次 LLM；新版合并为单次 LLM 调用，同时完成对话决策和记忆管理
- **移除对话状态机**：原版有潜水/冒泡/对话三种状态，由 LLM 评估意愿 + 随机阈值决定；新版由 LLM 自行决定是否发言
- **触发机制变更**：原版每 5-10 秒随机延迟处理；新版为攒够 5 条消息或 5 秒无新消息时触发

### 新增功能

- **表情包发送**：AI 从预配置的表情包列表中选择发送，通过 `MessageSegment.image()` 发送图片
- **表情包自动收集**：群聊中的图片经 VLM 分析后缓存，LLM 决定是否收藏，收藏时由 LLM 编写描述和关键词
- **图片理解双模式**：支持 `vlm` 模式（独立 VLM 分析）和 `llm` 模式（LLM 直接看图），通过 `AIGF_IMAGE_MODE` 配置
- **LLM 驱动的记忆系统**：
  - 短期记忆：对话摘要 + 临时信息，LLM 可增删改
  - 长期记忆：事件、知识，LLM 可增删改
  - 群友信息：按 QQ 号存储，LLM 可增删改 + 更新昵称
- **消息合并发送**：文本和 @ 消息合并为一条发送，表情包单独发送
- **默认预设**：首次运行自动生成可编辑的默认预设文件

### 文件变更

| 原文件 | 状态 | 说明 |
|--------|------|------|
| `__init__.py` | 重写 | 入口逻辑、触发机制、表情包缓存、发送逻辑 |
| `client.py` | 修改 | 新增 `images` 参数支持多模态消息 |
| `config.py` | 重写 | 参数前缀改为 `AIGF_`，新增图片模式、表情包配置，移除情绪/RAG 相关配置 |
| `image_manager.py` | 修改 | VLM 配置从 config 读取，LLM 模式下不初始化 VLM |
| `mem.py` | 修改 | 简化为 Message 数据类，新增 `user_id` 字段 |
| `presets.py` | 修改 | 改为异步加载，新增默认预设自动创建 |
| `session.py` | 重写 | 单次 LLM 调用 + 记忆操作执行 |
| `vlm.py` | 修改 | 模型和地址从 config 读取 |
| `emotion.py` | 删除 | 不再需要情绪系统 |
| `hippo_mem.py` | 删除 | 不再需要 HippoRAG |
| `impression.py` | 删除 | 不再需要印象记录 |
| `profile.py` | 删除 | 不再需要人物画像 |
| `siliconflow_embeddings.py` | 删除 | 不再需要嵌入模型 |
| `meme_manager.py` | 新建 | 表情包管理（缓存、收藏、发送、清理） |
| `memory.py` | 新建 | 记忆管理（短期/长期/群友，增删改操作） |

### 配置变更

| 原配置 | 新配置 | 说明 |
|--------|--------|------|
| `NYATURINGTEST_CHAT_OPENAI_API_KEY` | `AIGF_CHAT_OPENAI_API_KEY` | LLM API Key |
| `NYATURINGTEST_CHAT_OPENAI_MODEL` | `AIGF_CHAT_OPENAI_MODEL` | LLM 模型名称 |
| `NYATURINGTEST_CHAT_OPENAI_BASE_URL` | `AIGF_CHAT_OPENAI_BASE_URL` | LLM API 地址 |
| `NYATURINGTEST_SILICONFLOW_API_KEY` | — | 移除（不再需要硅基流动） |
| `NYATURINGTEST_VLM_ENABLED` | `AIGF_VLM_ENABLED` | 是否启用 VLM |
| `NYATURINGTEST_ENABLED_GROUPS` | `AIGF_ENABLED_GROUPS` | 启用的群号列表 |
| — | `AIGF_IMAGE_MODE` | 新增：图片理解模式（vlm/llm） |
| — | `AIGF_VLM_MODEL` | 新增：VLM 模型名称 |
| — | `AIGF_VLM_BASE_URL` | 新增：VLM API 地址 |
| — | `AIGF_VLM_API_KEY` | 新增：VLM API Key |
| — | `AIGF_MEME_ENABLED` | 新增：是否启用表情包 |
| — | `AIGF_MEME_MAX_COUNT` | 新增：表情包最大数量 |
| — | `AIGF_DEFAULT_PRESET` | 新增：默认预设名称 |

### 依赖变更

| 原依赖 | 状态 | 说明 |
|--------|------|------|
| `hipporag` | 移除 | 不再需要 RAG 框架 |
| `transformers` | 移除 | 不再需要 tokenizer |
| `numpy` | 可选 | 仅 GIF 处理时需要 |
| `nonebot2` | 保留 | 框架 |
| `nonebot-adapter-onebot` | 保留 | OneBot V11 适配器 |
| `nonebot-plugin-localstore` | 保留 | 文件存储 |
| `openai` | 保留 | LLM 调用 |
| `httpx` | 保留 | HTTP 请求 |
| `anyio` | 保留 | 异步文件 I/O |
| `pillow` | 保留 | 图片处理 |
| `pydantic` | 保留 | 配置验证 |

### 命令变更

|     原命令     | 状态 |       说明        |
| ------------- | ---- | ---------------- |
| `help`        | 保留 | 帮助信息          |
| `status`      | 保留 | 查看状态          |
| `set_role`    | 保留 | 设置角色          |
| `reset`       | 保留 | 重置会话          |
| `presets`     | 保留 | 查看预设          |
| `set_preset`  | 保留 | 加载预设          |
| `calm`        | 移除 | 不再有情绪系统     |
| `role`        | 移除 | 功能合并到 status |
| `list_groups` | 移除 | 仅保留群聊命令     |
| `reload_meme` | 新增 | 热重载表情包配置   |

