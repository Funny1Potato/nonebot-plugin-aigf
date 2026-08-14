# CHANGELOG

## AI-group-friend（基于 nonebot-plugin-nyaturingtest 重构）

### 架构变更

- **移除 HippoRAG**：删除基于知识图谱的长期记忆检索系统（`hippo_mem.py`、`siliconflow_embeddings.py`），改为 LLM 自主管理记忆
- **移除 VAD 情绪系统**：删除三维情感模型（`emotion.py`、`impression.py`、`profile.py`），用社交能量系统替代
- **移除三阶段对话流水线**：原版为"检索→反馈→对话"三阶段，每阶段各调一次 LLM；新版合并为单次 LLM 调用，同时完成对话决策和记忆管理
- **移除对话状态机**：原版有潜水/冒泡/对话三种状态，由 LLM 评估意愿 + 随机阈值决定；新版由社交能量 + LLM 自行决定是否发言
- **触发机制变更**：原版每 5-10 秒随机延迟处理；新版为攒够一定数量消息或超时后触发（数量和时间均可配置，默认 10 条 / 30 秒）
- **配置前缀变更**：`nyaturingtest_*` → `AIGF_*`
- **移除 SiliconFlow 依赖**：原版需要硅基流动 API Key 用于嵌入模型；新版不再需要
- **强制 JSON 输出**：新增 `AIGF_JSON_MODE` 配置，通过 `response_format` 确保 LLM 返回 JSON
- **Think 标签剥离**：`remove_leading_think()` 自动去除 LLM 输出中的 `<think>` 标签（兼容 Qwen 等模型）

### 新增功能

#### 表情包系统
- **表情包发送**：AI 从预配置的表情包列表中选择发送，通过 `MessageSegment.image()` 发送图片
- **表情包自动收集**：群聊中的图片经 VLM 分析后缓存，LLM 决定是否收藏，收藏时由 LLM 编写描述和关键词
- **双轨素材库**：管理员手动配置（`memes.json`）+ 自动收集（`collected.json`），管理员优先
- **缓存机制**：图片到达后先缓存到 `sticker_cache/`，LLM 处理后决定是否收藏
- **自动清理**：超过 `AIGF_MEME_MAX_COUNT` 上限时优先清理最近未使用的表情包

#### 社交能量系统
- 机器人拥有动态的"社交能量"（`social_energy`，范围 0.0~1.0，初始 0.75），替代原版的 VAD 情绪模型
- 每次消息处理时自然恢复（向基线 0.7 靠拢，可通过 `AIGF_ENERGY_BASELINE` 配置）+ 随机漂移（±0.08）
- 被 @ 时兴奋加成 +0.1，提升回复热情
- 回复后消耗能量：基础消耗 0.03 + 按回复文字长度增加（最多 0.15）
- 5 档能量描述注入 prompt：精力充沛 / 状态不错 / 一般般 / 有点懒 / 不想说话
- 形成自然的"话多→累了→安静→恢复→又想聊"周期

#### 四层记忆系统
- **短期记忆**：对话摘要 + 临时信息，LLM 可增删改，按群隔离存储
- **长期记忆**：事件、知识，LLM 可增删改，按群隔离存储
- **群友信息**：按 QQ 号全局共享存储，LLM 可增删改 info/aliases，系统自动更新 QQ 昵称和曾用昵称
- **文化记忆**：梗、网络用语、流行语，LLM 主动学习，根据聊天内容自动匹配注入 prompt

#### 联网搜索系统
- **两阶段模式**：LLM 先分析是否需要搜索，需要时调用搜索 API，再带搜索结果生成回复
- **Function Calling 模式**：LLM 自主决定是否调用搜索工具（需要模型支持 function calling）
- **Tavily API**（默认）：专为 AI 设计，返回格式友好（可选依赖 `tavily-python`）
- **Bocha AI**（备选）：国产 AI 搜索 API，中文搜索效果好，国内直连（无需额外依赖）
- **Bing Web Search**：微软必应搜索（无需额外依赖）
- **搜索结果重试**：LLM 返回非 JSON 且使用了搜索结果时，自动去掉搜索结果重试一次

#### 回复风格自然化
- Prompt 新增"回复风格"段落，指导 LLM 像发微信一样口语化
- 鼓励使用网络用语（"哈哈"、"233"、"确实"、"666"等）
- 回复长度有变化：有时一两个字，有时几句话
- 允许敷衍回复，不再对每条消息都认真回复

#### 消息合并
- 新增 `_merge_consecutive()` 方法，同一用户在合并窗口内的连续消息在 prompt 构建时合并
- 底层数据不修改，仅在展示给 LLM 时合并
- 解决群友分多次发送导致 LLM 看到碎片化上下文的问题

#### 不完整消息检测
- 纯 @ 消息或检测到同一用户连续发送（间隔 < `AIGF_MERGE_WINDOW`）时，使用更长的超时 `AIGF_INCOMPLETE_TIMEOUT`（默认 40 秒）
- 给用户更多时间发送完整内容，避免在消息未完成时触发处理

#### 其他新增
- **图片理解双模式**：`vlm` 模式（独立 VLM 分析）和 `llm` 模式（LLM 直接看图），通过 `AIGF_IMAGE_MODE` 配置
- **回复上下文理解**：消息中包含 reply 标记（`[回复 xxx 的消息: "yyy"]`），LLM 可理解对话回复关系
- **纯 @ 消息检测**：`Message` 新增 `is_at_only` 字段，识别纯 @ 消息并延长等待时间
- **Bot 回复记录**：bot 自己的文字、表情包、@ 回复都会存入最近消息，LLM 可看到自己之前说了什么
- **代理支持**：通过 `AIGF_PROXY_ENABLED`、`AIGF_HTTP_PROXY`、`AIGF_HTTPS_PROXY` 配置 HTTP 代理
- **启动日志增强**：启动时显示图片理解模式和联网搜索状态

### 移除功能

| 原版功能 | 说明 |
|---------|------|
| HippoRAG 长期记忆 | 替换为 LLM 自主管理的长期记忆 |
| VAD 三维情感模型 | 替换为社交能量系统 |
| 人物印象系统（PersonProfile） | 替换为群友信息（LLM 管理） |
| 对话状态机（潜水/冒泡/对话） | 替换为社交能量 + LLM 自主决策 |
| 三阶段流水线（检索→反馈→对话） | 合并为单次 LLM 调用 |
| 对话总结（chat_summary） | 功能被短期记忆和最近消息替代 |
| `help` / `帮助` 命令 | 群聊和私聊均已移除 |
| `calm` / `冷静` 命令 | 无情绪系统，不再需要 |
| `role` / `当前角色` 命令 | 功能合并到 `status` 命令 |
| `list_groups` 命令 | 私聊命令已移除 |
| 私聊命令支持 | 仅保留群聊命令 |
| SiliconFlow API Key | 不再需要嵌入模型 |
| 预设中的 relationships/events/bot_self 字段 | 简化为 name/role/knowledges/hidden |
| 会话状态持久化（JSON 文件） | 替换为 JSON 文件持久化记忆 |

### 配置变更

#### 移除的配置项

| 原配置项 | 说明 |
|---------|------|
| `nyaturingtest_chat_openai_api_key` | 替换为 `AIGF_CHAT_OPENAI_API_KEY` |
| `nyaturingtest_chat_openai_model` | 替换为 `AIGF_CHAT_OPENAI_MODEL` |
| `nyaturingtest_chat_openai_base_url` | 替换为 `AIGF_CHAT_OPENAI_BASE_URL` |
| `nyaturingtest_siliconflow_api_key` | 不再需要 |
| `nyaturingtest_vlm_enabled` | 替换为 `AIGF_VLM_ENABLED` |
| `nyaturingtest_enabled_groups` | 替换为 `AIGF_ENABLED_GROUPS` |

#### 新增的配置项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `AIGF_CHAT_OPENAI_API_KEY` | LLM API Key | 必填 |
| `AIGF_CHAT_OPENAI_BASE_URL` | LLM API 地址 | 必填 |
| `AIGF_CHAT_OPENAI_MODEL` | LLM 模型名称 | `gpt-3.5-turbo` |
| `AIGF_JSON_MODE` | 是否强制 LLM 输出 JSON | `true` |
| `AIGF_IMAGE_MODE` | 图片理解模式（vlm/llm） | `vlm` |
| `AIGF_VLM_ENABLED` | 是否启用 VLM | `true` |
| `AIGF_VLM_MODEL` | VLM 模型名称（vlm 模式必填） | 空 |
| `AIGF_VLM_BASE_URL` | VLM API 地址（vlm 模式必填） | 空 |
| `AIGF_VLM_API_KEY` | VLM API Key（为空时使用 chat key） | 空 |
| `AIGF_ENABLED_GROUPS` | 启用的群号列表 | `[]` |
| `AIGF_MEME_ENABLED` | 是否启用表情包功能 | `true` |
| `AIGF_MEME_MAX_COUNT` | 自动收集的表情包最大数量 | `200` |
| `AIGF_DEFAULT_PRESET` | 默认预设名称 | `default` |
| `AIGF_BATCH_COUNT` | 攒满多少条消息后触发 LLM 请求 | `10` |
| `AIGF_BATCH_TIMEOUT` | 距最后一条消息多少秒后触发 LLM 请求 | `30.0` |
| `AIGF_INCOMPLETE_TIMEOUT` | 检测到消息可能不完整时的等待时间（秒） | `40.0` |
| `AIGF_RECENT_MESSAGES` | prompt 中包含的最近历史消息条数 | `15` |
| `AIGF_MERGE_WINDOW` | 消息合并时间窗口（秒） | `5.0` |
| `AIGF_ENERGY_BASELINE` | 社交能量基线，能量会自然向此值回归（0.0~1.0） | `0.7` |
| `AIGF_SEARCH_ENABLED` | 是否启用联网搜索 | `false` |
| `AIGF_SEARCH_MODE` | 搜索模式: two_stage / function_call | `two_stage` |
| `AIGF_SEARCH_API` | 搜索API: tavily / bocha / bing | `tavily` |
| `AIGF_SEARCH_API_KEY` | 搜索 API Key | 空 |
| `AIGF_SEARCH_MAX_RESULTS` | 最大搜索结果数 | `3` |
| `AIGF_PROXY_ENABLED` | 是否启用代理 | `false` |
| `AIGF_HTTP_PROXY` | HTTP 代理地址 | 空 |
| `AIGF_HTTPS_PROXY` | HTTPS 代理地址 | 空 |

### 命令变更

| 原版命令 | 状态 | 说明 |
|---------|------|------|
| `help` / `帮助` | 移除 | 群聊和私聊均已移除 |
| `calm` / `冷静` | 移除 | 无情绪系统 |
| `role` / `当前角色` | 移除 | 功能合并到 `status` |
| `list_groups` / `群组列表` | 移除 | 私聊命令已移除 |
| `status` / `状态` | 保留 | 输出新增社交能量显示 |
| `set_role` / `设置角色` | 保留 | 用法不变 |
| `reset` / `重置` | 保留 | 用法不变 |
| `presets` / `preset` | 保留 | 用法不变 |
| `set_preset` / `set_presets` | 保留 | 用法不变 |
| `reload_meme` / `重载表情包` | 新增 | 热重载表情包配置 |

### Prompt 变更

| 原版 Prompt | 状态 | 说明 |
|------------|------|------|
| 三阶段 Prompt（检索/反馈/对话） | 重写 | 合并为单次调用的统一 Prompt |
| VAD 情绪注入 | 移除 | 替换为社交能量描述 |
| 人物印象注入 | 移除 | 替换为群友信息 JSON |
| HippoRAG 检索结果注入 | 移除 | 替换为联网搜索结果（可选） |
| 对话状态机逻辑 | 移除 | 替换为回复决策规则 |

| 新增 Prompt 段落 | 说明 |
|-----------------|------|
| `## 回复风格` | 指导 LLM 口语化、简短、有变化地回复 |
| `## 当前状态` | 展示社交能量描述，影响回复决策 |
| `## 你的知识` | 注入预设知识 |
| `## 相关文化知识` | 展示当前聊天中涉及的文化词汇 |
| `## 搜索结果` | 展示搜索到的信息（仅搜索时） |
| `## 可用的表情包` | 展示可供发送的表情包列表 |
| `## 当前消息中出现的图片` | 展示可收藏的缓存表情包 |
| `## 理解群聊对话` | 教 LLM 通过 @、reply、时间推断对话关系 |
| `## 图片消息说明` | 指导 LLM 不要主动评论图片 |
| `## 回复决策` | 能量感知的自然决策指导 |
| `## 文化记忆` | 文化记忆操作说明 |

### 文件变更

| 原版文件 | 状态 | 说明 |
|---------|------|------|
| `__init__.py` | 重写 | 入口逻辑、触发机制、表情包缓存、reply 提取、发送逻辑、纯 @ 检测 |
| `client.py` | 修改 | 新增 `images` 参数支持多模态、`generate_response_with_tools()` 支持 Function Calling、`response_format` 强制 JSON、`remove_leading_think()` |
| `config.py` | 重写 | 配置前缀改为 `AIGF_`，新增图片模式、表情包、搜索、社交能量等配置 |
| `image_manager.py` | 修改 | VLM 配置从 config 读取，LLM 模式下不初始化 VLM，优化 VLM prompt |
| `mem.py` | 修改 | 简化为 Message 数据类，新增 `user_id`、`is_at_only` 字段 |
| `presets.py` | 修改 | 改为异步加载，新增默认预设自动创建，支持 `utf-8-sig` 编码，预设字段简化 |
| `session.py` | 重写 | 单次 LLM 调用 + 社交能量 + 消息合并 + 搜索集成 + 文化记忆 + prompt 构建 |
| `vlm.py` | 修改 | 模型和地址从 config 读取，移除 SiliconFlow 硬编码 |
| `emotion.py` | 删除 | 不再需要 VAD 情绪系统 |
| `hippo_mem.py` | 删除 | 不再需要 HippoRAG |
| `impression.py` | 删除 | 不再需要印象记录 |
| `profile.py` | 删除 | 不再需要人物画像 |
| `siliconflow_embeddings.py` | 删除 | 不再需要嵌入模型 |
| `meme_manager.py` | 新建 | 表情包管理（缓存、收藏、发送、清理） |
| `memory.py` | 新建 | 记忆管理（短期/长期/群友/文化，增删改操作，按群隔离） |
| `search.py` | 新建 | 搜索客户端（Tavily + Bocha + Bing），Bocha/Bing 使用 httpx 异步请求 |

