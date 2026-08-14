<div align="center">
    <a href="https://v2.nonebot.dev/store">
    <img src="https://raw.githubusercontent.com/fllesser/nonebot-plugin-template/refs/heads/resource/.docs/NoneBotPlugin.svg" width="310" alt="logo"></a>

## ✨ AI-group-friend ✨

群聊特化 LLM 聊天机器人，具有 LLM 驱动的记忆系统和表情包功能。

<p>
    <a href="https://github.com/shadow3aaa/nonebot-plugin-nyaturingtest">
    </a>
    <a href="./LICENSE"><img src="https://img.shields.io/github/license/shadow3aaa/nonebot-plugin-nyaturingtest?style=flat-square" alt="license"></a>
    <img src="https://img.shields.io/badge/python-3.10+-blue?style=flat-square&logo=python&logoColor=white" alt="python">
</p>
</div>

## 📖 介绍

> 基于 [shadow3aaa/nonebot-plugin-nyaturingtest](https://github.com/shadow3aaa/nonebot-plugin-nyaturingtest) 重构，移除了 HippoRAG 和情绪系统，改为 LLM 自主管理记忆，并添加表情包存储和发送功能。
* 本项目对原项目代码的修改及重构均有AI高度参与，若有做得不够好的地方，请手下留情。

### 特点:

- 🎭 **社交能量系统**：动态能量影响回复意愿，形成自然的"话多→累了→安静→恢复"周期
- 🧠 **四层记忆系统**：短期记忆、长期记忆、群友信息、文化记忆，LLM 自主增删改
- 🔍 **联网搜索**：支持 Tavily / Bocha / Bing，自动搜索不懂的梗和网络用语
- 🖼️ **表情包功能**：AI 自主决定发表情包；自动从群聊中收藏表情包
- 📨 **消息合并**：同一用户连续消息自动合并，避免碎片化上下文
- ⏱️ **不完整消息检测**：纯 @ 消息或连续发送时自动延长等待时间
- 🔒 **支持强制 JSON 输出**：通过 response_format 确保 LLM 始终返回正确格式
- ⚡ **轻量高效**：单次 LLM 调用完成对话 + 记忆管理，节约 token

## 💿 安装

> [!IMPORTANT]
> 要使用本插件, 你至少需要
>
> - 一个有效的 openai 规范接口 api key (根据你的 base_url，可以不是 openai 的)，你需要在 `.env` 文件中配置对应的 api 地址

<details open>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装（暂时不行，还未上架）

    nb plugin install nonebot-plugin-aigf --upgrade

</details>

<details>
<summary>使用包管理器安装</summary>

```bash
pip install nonebot-plugin-aigf
```

在 `pyproject.toml` 中添加：

```toml
[tool.nonebot]
plugins = ["nonebot-plugin-aigf"]
```

</details>

## 配置

在 `.env.prod` 中添加：

### 必填

```env
AIGF_CHAT_OPENAI_API_KEY="sk-xxxxxxxxxxxx"                         # LLM API Key
AIGF_CHAT_OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"  # LLM API 地址
AIGF_CHAT_OPENAI_MODEL="qwen-plus"                                 # LLM 模型名称
AIGF_ENABLED_GROUPS=[123456, 789012]                               # 启用的群号列表
```

### 可选

```env
# --- 基础 ---
AIGF_MEME_ENABLED=true                 # 是否启用表情包功能（默认 true）
AIGF_MEME_MAX_COUNT=200                # 自动收集的表情包最大数量（默认 200）
AIGF_DEFAULT_PRESET=default            # 默认预设名称（默认 "default"）

# --- 请求控制 ---
AIGF_BATCH_COUNT=10                    # 攒满多少条消息后触发 LLM 请求（默认 10）
AIGF_BATCH_TIMEOUT=30.0                # 距最后一条消息多少秒后触发（默认 30.0）
AIGF_INCOMPLETE_TIMEOUT=40.0           # 检测到消息可能不完整时的等待时间/秒（纯@消息或连续发送，默认 40.0）
AIGF_RECENT_MESSAGES=15                # prompt 中包含的最近历史消息条数（默认 15）
AIGF_MERGE_WINDOW=5.0                  # 消息合并时间窗口/秒（默认 5.0）

# --- LLM ---
AIGF_JSON_MODE=true                    # 是否强制 LLM 输出 JSON（默认 true，需要模型支持 response_format）
AIGF_ENERGY_BASELINE=0.7               # 社交能量基线，能量会自然向此值回归（默认 0.7，范围 0.0~1.0）

# --- 联网搜索 ---
AIGF_SEARCH_ENABLED=false              # 是否启用联网搜索（默认 false）
AIGF_SEARCH_MODE="two_stage"             # 搜索模式: two_stage / function_call（默认 two_stage）
AIGF_SEARCH_API="tavily"                 # 搜索API: tavily / bocha / bing（默认 tavily）
AIGF_SEARCH_API_KEY=""                 # 搜索 API Key（tavily/bocha/bing 必填）
AIGF_SEARCH_MAX_RESULTS=3              # 最大搜索结果数（默认 3）

# --- 代理 ---
AIGF_PROXY_ENABLED=false               # 是否启用代理（默认 false）
AIGF_HTTP_PROXY="http://127.0.0.1:7890"   # HTTP 代理地址
AIGF_HTTPS_PROXY="http://127.0.0.1:7890"  # HTTPS 代理地址

# --- 图片理解（VLM） ---
AIGF_IMAGE_MODE="vlm"                             # 图片模式: vlm=独立VLM分析, llm=LLM直接看图（默认 vlm）
AIGF_VLM_ENABLED=true                             # 是否启用VLM（仅 vlm 模式有效，默认 true）
AIGF_VLM_MODEL="qwen3.6-plus"                                          # VLM 模型名称（vlm 模式必填）
AIGF_VLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"   # VLM API 地址（vlm 模式必填）
AIGF_VLM_API_KEY=""                               # VLM API Key（为空时使用 chat 的 key）
```

## 触发机制

- 攒够 **10 条**新消息，或最后一条消息后 **30 秒**内无新消息，触发一次处理（可通过配置调整）
- 纯 @ 消息或检测到同一用户连续发送（间隔 < `AIGF_MERGE_WINDOW`）时，等待时间延长至 `AIGF_INCOMPLETE_TIMEOUT`（默认 40 秒），给用户更多时间发送完整内容
- 消息合并窗口内的同一用户连续消息会被合并为一条展示给 LLM
- 每次处理时，LLM 收到最近 **15 条**聊天记录（可配置） + 四层记忆 + 预设 + 表情包列表
- LLM 一次调用同时完成：回复决策 + 记忆管理 + 表情包选择

## 社交能量系统

机器人拥有动态的"社交能量"（`social_energy`，范围 0.0~1.0，初始 0.75），影响回复意愿和热情程度：

| 能量范围 | 状态描述 | 表现 |
|---------|---------|------|
| ≥ 0.8 | 精力充沛 | 看到什么都想插嘴 |
| ≥ 0.6 | 状态不错 | 有兴趣的话题会主动参与 |
| ≥ 0.4 | 一般般 | 有人找就回，不太主动 |
| ≥ 0.2 | 有点懒 | 倾向于潜水 |
| < 0.2 | 不想说话 | 完全不想说话 |

- 每次消息处理时自然恢复（向基线 0.7 靠拢，可通过 `AIGF_ENERGY_BASELINE` 配置）+ 随机漂移（±0.08）
- 被 @ 时兴奋加成 +0.1，提升回复热情
- 回复后消耗能量：基础消耗 0.03 + 按回复文字长度增加（最多 0.15）
- 形成自然的"话多→累了→安静→恢复→又想聊"周期

## 联网搜索系统

让机器人能够主动搜索不懂的梗/网络用语，弥补大模型知识延迟问题。

### 搜索模式

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `two_stage`（默认） | LLM 先分析是否需要搜索，需要时调用搜索 API，再带搜索结果生成回复 | 所有模型 |
| `function_call` | LLM 自主决定是否调用搜索工具 | 需要模型支持 function calling |

推荐使用 `function_call` 模式，LLM能够更好地利用搜索工具。

### 搜索 API

| API | 说明 | 额外依赖 |
|-----|------|---------|
| `tavily`（默认） | 专为 AI 设计，返回格式友好 | `tavily-python` |
| `bocha` | 国产 AI 搜索 API，中文搜索效果好，国内直连 | 无 |
| `bing` | 微软必应搜索 | 无 |

### 搜索结果重试

当搜索结果触发 LLM 内容安全审核或格式问题时，自动去掉搜索结果重试一次，确保机器人能正常回复。

## 对话理解

机器人通过以下方式理解群聊中的对话关系：

- **reply 标记**：消息中包含 `[回复 xxx 的消息: "yyy"]`，表示在回复某人
- **@ 提及**：`@某人` 表示消息是发给那个人的
- **时间推断**：时间接近的消息通常在互相回复

**回复决策规则**：
- 社交能量 + 话题兴趣度驱动，不再机械地响应所有 @ 和提及
- 有人 @ 了机器人 → 通常回复（但能量很低时也可能敷衍一下）
- 有人回复了机器人之前的消息 → 回复
- 消息明显是对所有人说的，且有值得补充的内容 → 回复
- 不确定是否在和自己说话 → **不回复**

## 记忆系统

机器人拥有四层记忆，由 LLM 在每次回复时自主管理：

### 短期记忆

存储在 `<插件数据目录>/memory/<群号>/short_term.json`，内容为 LLM 维护的信息列表，包括对话摘要、临时上下文、有趣的梗等。LLM 可以添加、修改、删除条目。

### 长期记忆

存储在 `<插件数据目录>/memory/<群号>/long_term.json`，内容为 LLM 认为值得长期记住的信息，如群内发生的事件、群规、群友分享的有用知识等。LLM 可添加、修改、删除。不应记录临时对话或常识信息。

### 群友信息

存储在 `<插件数据目录>/memory/friends/<QQ号>.json`，每个群友一个文件，以 QQ 号命名。LLM 记录群友的昵称、职业、爱好、说过的话、与其他群友的关系等。

| 字段 | 来源 | 说明 |
|------|------|------|
| `nickname` | 系统自动更新 | QQ 全局昵称 |
| `aliases` | LLM 管理 | 群友对 ta 的称呼 |
| `past_nicknames` | 系统自动记录 | 曾用 QQ 昵称 |
| `info` | LLM 管理 | 一般信息（职业、爱好等） |
| `groups` | 系统自动维护 | 所在的群列表 |

### 文化记忆

存储在 `<插件数据目录>/memory/<群号>/culture.json`，记录梗、网络用语、流行语。LLM 主动学习和存储，根据聊天内容自动匹配。

## 表情包功能

### 工作原理

```
群聊中有人发图片/表情包
    ↓
下载图片 → VLM 分析内容和情感
    ↓
保存到缓存目录（<缓存目录>/sticker_cache/）
    ↓
下一次消息处理时，LLM 在 Prompt 中看到缓存的表情包
    ↓
LLM 决定是否收藏 → 保存到 memes 目录
```

### 表情包素材库

存放在 `<插件数据目录>/memes/` 下：

```
memes/
├── memes.json          ← 管理员手动配置
├── collected.json      ← 机器人自动收集
└── *.jpg/png/gif       ← 表情包图片文件
```

#### 管理员手动配置

编辑 `memes.json`：

```json
[
  {
    "id": "happy_spin",
    "path": "happy_spin.jpg",
    "keywords": ["开心", "高兴", "庆祝"],
    "description": "开心到转圈的小人"
  }
]
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | ✅ | 唯一标识符，AI 用这个选择表情包 |
| `path` | ✅ | 图片文件名（相对于 memes 目录） |
| `keywords` | ✅ | 适用场景关键词 |
| `description` | ✅ | 一句话描述内容 |

修改后执行 `/重载表情包` 即可生效，无需重启。

#### 自动收集

机器人收到图片时，VLM 分析后保存到缓存。LLM 在回复时看到缓存的表情包，决定是否收藏。

- 图片按 MD5 hash 去重
- 超过 `AIGF_MEME_MAX_COUNT` 上限时，优先清理最近未使用的
- 缓存中的表情包只处理一次，处理后清空

## 图片理解模式

通过 `AIGF_IMAGE_MODE` 配置：

| 模式 | 流程 | 适用场景 |
|------|------|---------|
| `vlm`（默认） | 图片 → VLM 分析 → 文字描述给 LLM | LLM 不支持图片输入 |
| `llm` | 图片 → base64 直接附在 LLM prompt 中 | LLM 支持视觉（GPT-4o 等） |

## 预设系统

首次运行后在 `<插件配置目录>/presets/` 下生成 `default.json`：

```json
{
  "name": "小助手",
  "role": "一个友好的群聊助手，会用轻松的语气和大家聊天",
  "knowledges": [],
  "hidden": false
}
```

在 `presets/` 目录下创建新的 JSON 文件即可添加新预设，执行 `set_preset <预设名>` 加载。

## 消息格式

LLM 支持以下回复类型：

| 类型 | 格式 | 说明 |
|------|------|------|
| 文本 | `{"type": "text", "content": "..."}` | 纯文本消息 |
| @ | `{"type": "at", "name": "群友昵称"}` | 艾特群友 |
| 表情包 | `{"type": "meme", "id": "表情包id"}` | 发送表情包 |

文本和 @ 会合并为一条消息发送，表情包单独发送。

## 一些碎碎念
- 本项目移除了原插件的 HippoRAG 和情绪系统，直接使用LLM进行记忆处理，拟人程度不如原插件
- 本项目的token消耗理论上相较原插件能减少约30-50%，但绝对值仍不低，每次请求约消耗 10-20K tokens，在记忆数据丰富之后会更高
- 推荐使用价格较为低廉的模型作为llm模型（群友就是要笨笨的才可爱呀），再以识图能力较好的vlm模型作为辅助（要是看不懂表情包还是会比较尴尬的）
