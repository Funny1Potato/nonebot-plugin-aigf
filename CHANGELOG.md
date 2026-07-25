# CHANGELOG

## AI-group-friend（基于 nonebot-plugin-nyaturingtest 重构）

### 架构变更

- **移除 HippoRAG**：删除基于知识图谱的长期记忆检索系统（`hippo_mem.py`、`siliconflow_embeddings.py`），改为 LLM 自主管理记忆
- **移除情绪系统**：删除 VAD 三维情感模型（`emotion.py`、`impression.py`、`profile.py`）
- **移除三阶段对话流水线**：原版为"检索→反馈→对话"三阶段，每阶段各调一次 LLM；新版合并为单次 LLM 调用，同时完成对话决策和记忆管理
- **移除对话状态机**：原版有潜水/冒泡/对话三种状态，由 LLM 评估意愿 + 随机阈值决定；新版由 LLM 自行决定是否发言
- **触发机制变更**：原版每 5-10 秒随机延迟处理；新版为攒够 5 条消息或 10 秒无新消息时触发

### 新增功能

- **表情包发送**：AI 从预配置的表情包列表中选择发送，通过 `MessageSegment.image()` 发送图片
- **表情包自动收集**：群聊中的图片经 VLM 分析后缓存，LLM 决定是否收藏，收藏时由 LLM 编写描述和关键词
- **图片理解双模式**：支持 `vlm` 模式（独立 VLM 分析）和 `llm` 模式（LLM 直接看图），通过 `AIGF_IMAGE_MODE` 配置
- **LLM 驱动的记忆系统**：
  - 短期记忆：对话摘要 + 临时信息，LLM 可增删改，按群隔离
  - 长期记忆：事件、知识，LLM 可增删改，按群隔离
  - 群友信息：按 QQ 号全局共享存储，LLM 可增删改 info/aliases，系统自动更新 QQ 昵称和曾用昵称
- **群友信息独立存储**：群友信息全局共享，用 `groups` 字段标记所在群，跨群也能识别同一用户
- **回复上下文理解**：消息中包含 reply 标记（`[回复 xxx 的消息: "yyy"]`），LLM 可理解对话回复关系
- **对话理解指令**：prompt 中教 LLM 通过 @、reply 标记、时间推断对话关系，不确定时不回复
- **消息合并发送**：文本和 @ 消息合并为一条发送，表情包单独发送
- **默认预设**：首次运行自动生成可编辑的默认预设文件
- **Bot 回复记录**：bot 自己的文字、表情包、@ 回复都会存入最近消息，LLM 可看到自己之前说了什么
- **完善的日志系统**：DEBUG/INFO/SUCCESS 三级日志，覆盖消息接收、VLM 分析、缓存、记忆操作、消息发送全流程

### 表情包系统

- **双轨素材库**：管理员手动配置（`memes.json`）+ 自动收集（`collected.json`），管理员优先
- **缓存机制**：图片到达后先缓存到 `sticker_cache/`，LLM 处理后决定是否收藏
- **VLM 优化**：描述 prompt 限制 50 字，情感 prompt 只输出 3 个词，不识别具体角色名称（只描述外貌特征）
- **自动清理**：超过 `AIGF_MEME_MAX_COUNT` 上限时优先清理最近未使用的表情包
- **缓存防重**：图片按 MD5 hash 去重，LLM 返回的 id 必须在当前缓存中才生效

### 记忆系统

- **JSON 格式展示**：prompt 中记忆以 JSON 数组/对象格式展示，LLM 可直接看到 index 对应关系
- **积极管理指令**：prompt 中明确要求 LLM 主动增删改记忆，附带具体场景示例
- **群友信息字段**：
  - `nickname`：QQ 全局昵称（系统自动更新）
  - `aliases`：群友对 ta 的称呼（LLM 管理，`add_alias`/`remove_alias`）
  - `past_nicknames`：曾用 QQ 昵称（系统自动记录）
  - `info`：一般信息（LLM 管理，`add`/`modify`/`delete`）
  - `groups`：所在的群列表（系统自动维护）
- **昵称处理**：统一使用 QQ 全局昵称，不使用群名片

### 文件变更

| 原文件 | 状态 | 说明 |
|--------|------|------|
| `__init__.py` | 重写 | 入口逻辑、触发机制、表情包缓存、reply 提取、发送逻辑 |
| `client.py` | 修改 | 新增 `images` 参数支持多模态消息 |
| `config.py` | 重写 | 参数前缀改为 `AIGF_`，新增图片模式、表情包配置，移除情绪/RAG 相关配置 |
| `image_manager.py` | 修改 | VLM 配置从 config 读取，LLM 模式下不初始化 VLM，优化 VLM prompt |
| `mem.py` | 修改 | 简化为 Message 数据类，新增 `user_id` 字段 |
| `presets.py` | 修改 | 改为异步加载，新增默认预设自动创建，支持 `utf-8-sig` 编码 |
| `session.py` | 重写 | 单次 LLM 调用 + 记忆操作执行 + 对话理解 + 回复决策 |
| `vlm.py` | 修改 | 模型和地址从 config 读取 |
| `emotion.py` | 删除 | 不再需要情绪系统 |
| `hippo_mem.py` | 删除 | 不再需要 HippoRAG |
| `impression.py` | 删除 | 不再需要印象记录 |
| `profile.py` | 删除 | 不再需要人物画像 |
| `siliconflow_embeddings.py` | 删除 | 不再需要嵌入模型 |
| `meme_manager.py` | 新建 | 表情包管理（缓存、收藏、发送、清理） |
| `memory.py` | 新建 | 记忆管理（短期/长期/群友，增删改操作，按群隔离） |

### 配置项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `AIGF_CHAT_OPENAI_API_KEY` | LLM API Key | 必填 |
| `AIGF_CHAT_OPENAI_MODEL` | LLM 模型名称 | `gpt-3.5-turbo` |
| `AIGF_CHAT_OPENAI_BASE_URL` | LLM API 地址 | `https://api.openai.com/v1` |
| `AIGF_IMAGE_MODE` | 图片理解模式（vlm/llm） | `vlm` |
| `AIGF_VLM_ENABLED` | 是否启用 VLM | `true` |
| `AIGF_VLM_MODEL` | VLM 模型名称 | `Pro/Qwen/Qwen2.5-VL-7B-Instruct` |
| `AIGF_VLM_BASE_URL` | VLM API 地址 | `https://api.siliconflow.cn/v1` |
| `AIGF_VLM_API_KEY` | VLM API Key（为空时使用 chat key） | 空 |
| `AIGF_ENABLED_GROUPS` | 启用的群号列表 | `[]` |
| `AIGF_MEME_ENABLED` | 是否启用表情包功能 | `true` |
| `AIGF_MEME_MAX_COUNT` | 自动收集的表情包最大数量 | `200` |
| `AIGF_DEFAULT_PRESET` | 默认预设名称 | `default` |

### 依赖

```
nonebot2, nonebot-adapter-onebot, nonebot-plugin-localstore,
openai, httpx, anyio, pillow, pydantic, numpy
```

移除：`hipporag`、`transformers`


### 日志系统

| 级别 | 用途 |
|------|------|
| SUCCESS | 消息接收、消息发送、表情包缓存/收藏成功、启动信息 |
| INFO | VLM 返回结果、记忆操作类型、表情包缓存、群友昵称更新 |
| DEBUG | spawn_state 触发、消息解析、LLM 调用/返回、记忆操作详情、缓存查找 |
| WARNING | 缓存未找到、VLM 未启用、预设加载失败 |
| ERROR | 发送失败、记忆操作失败、图片处理错误 |
