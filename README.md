<div align="center">
    <a href="https://v2.nonebot.dev/store">
    <img src="https://raw.githubusercontent.com/fllesser/nonebot-plugin-template/refs/heads/resource/.docs/NoneBotPlugin.svg" width="310" alt="logo"></a>

## ✨ nonebot-plugin-aigf ✨

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

### 特点:

- 🧠 **LLM 驱动的记忆系统**：短期记忆、长期记忆、群友信息，LLM 自主增删改
- 🖼️ **表情包功能**：AI 自主决定发表情包；自动从群聊中收藏表情包（缓存机制）
- 🔍 **图片理解**：通过 VLM 或多模态大模型理解群友发的图片和表情包
- 📝 **预设系统**：支持角色预设，含可编辑的默认预设
- ⚡ **轻量高效**：单次 LLM 调用完成对话 + 记忆管理，减少token消耗

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

```env
# === 必填 ===
AIGF_CHAT_OPENAI_API_KEY="***"         # LLM API Key
AIGF_CHAT_OPENAI_BASE_URL="***"  # LLM API 地址
AIGF_CHAT_OPENAI_MODEL="***"  # LLM 模型名称

# === 可选 ===
AIGF_ENABLED_GROUPS=[123456, 789012]   # 启用的群号列表
AIGF_MEME_ENABLED=true                 # 是否启用表情包功能（默认 true）
AIGF_MEME_MAX_COUNT=200                # 自动收集的表情包最大数量（默认 200）
AIGF_DEFAULT_PRESET=default            # 默认预设名称（默认 "default"）

# === VLM 配置（图片理解） ===
# === 图片理解 ===
AIGF_IMAGE_MODE="vlm"                             # 图片模式: vlm=独立VLM分析, llm=LLM直接看图
AIGF_VLM_ENABLED=true                           # 是否启用VLM（仅 vlm 模式有效，默认 true）
AIGF_VLM_MODEL="Pro/Qwen/Qwen2.5-VL-7B-Instruct" # VLM 模型名称
AIGF_VLM_BASE_URL="https://api.siliconflow.cn/v1" # VLM API 地址
AIGF_VLM_API_KEY="***"                           # VLM API Key（为空时使用 chat 的 key）
```

## 命令

| 命令 | 说明 | 权限 |
|------|------|------|
| `help` / `帮助` | 显示帮助信息 | SUPERUSER |
| `status` / `状态` | 查看机器人状态（角色、最近消息） | SUPERUSER |
| `set_role <名字> <设定>` | 设置机器人角色 | SUPERUSER |
| `reset` / `重置` | 重置会话（清空所有记忆） | SUPERUSER |
| `presets` | 查看可用的角色预设 | SUPERUSER |
| `set_preset <预设名>` | 加载指定的角色预设 | SUPERUSER |
| `reload_meme` / `重载表情包` | 热重载表情包配置 | SUPERUSER |

## 触发机制

- 攒够 **5 条**新消息，或最后一条消息后 **5 秒**内无新消息，触发一次处理
- 每次处理时，LLM 收到最近 **10 条**聊天记录 + 三层记忆 + 预设 + 表情包列表
- LLM 一次调用同时完成：回复决策 + 记忆管理 + 表情包选择

## 记忆系统

机器人拥有三层记忆，由 LLM 在每次回复时自主管理：

### 短期记忆

存储在 `<插件数据目录>/memory/short_term.json`，内容为 LLM 维护的信息列表，包括对话摘要、临时上下文、有趣的梗等。LLM 可以添加、修改、删除条目，内容可以详细一些。

### 长期记忆

存储在 `<插件数据目录>/memory/long_term.json`，内容为 LLM 认为值得长期记住的信息，如群内发生的事件、群规、群友分享的有用知识等。

### 群友信息

存储在 `<插件数据目录>/memory/friends/<QQ号>.json`，每个群友一个文件，以 QQ 号命名。LLM 记录群友的昵称、职业、爱好、说过的话、与其他群友的关系等。当群友修改昵称时，LLM 可通过 `update_name` 更新。

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

机器人收到图片时，VLM 分析后保存到缓存。LLM 在回复时看到缓存的表情包，决定是否收藏：

```json
{
  "memory": {
    "save_meme": {"id": "a1b2c3d4e5f6", "description": "开心转圈的小人"}
  }
}
```

支持一次收藏多个：
```json
{
  "memory": {
    "save_meme": [
      {"id": "a1b2c3d4e5f6", "description": "开心转圈"},
      {"id": "e7f8g9h0i1j2", "description": "气鼓鼓"}
    ]
  }
}
```

#### 缓存机制

- 图片缓存在 `<缓存目录>/sticker_cache/`，用图片内容的 MD5 作文件名，自动去重
- 超过 7 天的缓存文件会自动清理
- 自动收集的表情包超过 `AIGF_MEME_MAX_COUNT` 上限时，优先清理最近未使用的

#### 发送表情包

LLM 在回复中指定表情包 id（来自 memes.json 或 collected.json）：

```json
{"type": "meme", "id": "happy_spin"}
```

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

### 预设字段

| 字段 | 说明 |
|------|------|
| `name` | 角色名称 |
| `role` | 角色设定 |
| `knowledges` | 预设知识列表（会注入 Prompt） |
| `hidden` | 是否在 `/presets` 中隐藏 |

### 添加新预设

在 `presets/` 目录下创建新的 JSON 文件，如 `猫娘.json`：

```json
{
  "name": "喵喵",
  "role": "一个可爱的群猫娘，群里的其它人是你的主人",
  "knowledges": [
    "猫娘有猫耳和猫尾巴",
    "猫娘喜欢吃鱼"
  ],
  "hidden": false
}
```

然后在群内执行 `set_preset 猫娘` 即可加载。

## 消息格式

LLM 支持以下回复类型：

| 类型 | 格式 | 说明 |
|------|------|------|
| 文本 | `{"type": "text", "content": "..."}` | 纯文本消息 |
| @ | `{"type": "at", "name": "群友昵称"}` | 艾特群友 |
| 表情包 | `{"type": "meme", "id": "表情包id"}` | 发送表情包 |

文本和 @ 会合并为一条消息发送，表情包单独发送。也可以直接用纯字符串代替 `{"type": "text", "content": "..."}`。

## 图片理解模式

支持两种图片理解模式，通过 `AIGF_IMAGE_MODE` 配置：

### VLM 模式（默认）

```
图片 → VLM 分析 → 缓存描述 → 文字 prompt 给 LLM
```

- LLM 不需要支持图片输入
- VLM 单独调用，消耗较少 token
- 适合 LLM 不支持视觉的场景

### LLM 模式

```
图片 → 直接以 base64 附在 LLM prompt 中 → LLM 看图决策
```

- LLM 直接看到图片，理解更准确
- 不需要配置 VLM
- 适合支持视觉的模型（如 GPT-4o、Qwen-VL）
- 图片 base64 会消耗更多 token

## 依赖

- NoneBot2 + OneBot V11 适配器
- OpenAI 兼容 API（LLM）
- VLM API（图片理解，可选）
- Pillow（图片处理）
- httpx、anyio
