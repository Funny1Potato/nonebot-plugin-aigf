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

> ⚠️ **注意**：该 beta 测试版本内容已上线正式版，请勿使用该版本。

## 📖 介绍

群聊特化 LLM 聊天机器人 **beta 测试版**，在 v0.3.2 基础上增加了拟人化增强功能。

> ⚠️ **注意**：这是 beta 测试版本，用于测试新功能。安装方式为**覆盖安装**，会替换现有的 nonebot-plugin-aigf。

## 🆕 Beta 版新增特性

### 🎭 社交能量系统
机器人拥有动态的"社交能量"（0.0~1.0），影响回复意愿和热情程度：
- **精力充沛**（≥0.8）：看到什么都想插嘴
- **状态不错**（≥0.6）：有兴趣的话题会主动参与
- **一般般**（≥0.4）：有人找就回，不太主动
- **有点懒**（≥0.2）：倾向于潜水
- **不想说话**（<0.2）：完全不想说话

能量会自然恢复，回复后消耗（回复越长消耗越多），形成自然的"话多→累了→安静→恢复"周期。

### 💬 回复风格自然化
- 像发微信一样口语化，不再写正式段落
- 回复长度有变化：有时一两个字，有时几句话
- 可以使用网络用语（"哈哈"、"233"、"确实"等）
- 允许敷衍回复（"嗯嗯"、"哈哈哈"）
- 不再对每条消息都认真回复

### 📨 消息合并
群友连续发送的多条消息会被自动合并为一条，避免 LLM 看到碎片化的上下文：
- 同一用户在 `AIGF_MERGE_WINDOW`（默认 5 秒）内的连续消息合并显示
- 智能触发延迟：检测到连续发送时等待完整消息再处理

### 🔍 联网搜索系统
让机器人能够主动搜索不懂的梗/网络用语，弥补大模型知识延迟问题：
- **两阶段模式**：LLM 先分析是否需要搜索，需要时调用搜索 API
- **Function Calling 模式**：LLM 自主决定是否调用搜索工具（需要模型支持）
- 支持多种搜索 API：**Tavily**（默认）、**DuckDuckGo**（免费）、**Bing**

### 🧠 文化记忆系统
第四层记忆，专门存储梗、网络用语、流行语：
- LLM 主动识别并提取新的文化词汇
- 通过搜索学到的梗会自动存入文化记忆
- 根据当前聊天内容匹配相关的文化知识注入 prompt
- 让机器人能够理解和跟上群内的梗

### 🧠 选择性回复
基于社交能量和话题兴趣度决定是否回复，不再机械地响应所有 @ 和提及。

## 📖 原有特性（v0.3.2）

- 🧠 **LLM 驱动的记忆系统**：短期记忆、长期记忆、群友信息，LLM 自主增删改
- 🖼️ **表情包功能**：AI 自主决定发表情包；自动从群聊中收藏表情包
- 🔍 **图片理解**：支持 VLM 模式和 LLM 直接看图模式
- 📝 **预设系统**：支持角色预设，含可编辑的默认预设
- ⚡ **轻量高效**：单次 LLM 调用完成对话 + 记忆管理

## 💿 安装（覆盖安装）

> ⚠️ **重要**：Beta 版采用覆盖安装方式，会替换现有的 nonebot-plugin-aigf。建议先备份原有配置和数据。

### pip 覆盖安装

```bash
# 卸载旧版本（如果有）
pip uninstall nonebot-plugin-aigf

# 安装 beta 版
pip install nonebot-plugin-aigf==0.4.0b1
```


### 配置

在 `.env.prod` 中添加：

#### 必填（与原版相同）

```env
AIGF_CHAT_OPENAI_API_KEY="sk-xxxxxxxxxxxx"
AIGF_CHAT_OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
AIGF_CHAT_OPENAI_MODEL="qwen-plus"
AIGF_ENABLED_GROUPS=[123456, 789012]
```

#### Beta 版新增配置

```env
# --- 消息合并 ---
AIGF_MERGE_WINDOW=5.0                  # 消息合并时间窗口/秒（默认 5.0）

# --- 联网搜索 ---
AIGF_SEARCH_ENABLED=false              # 是否启用联网搜索（默认 false）
AIGF_SEARCH_MODE=two_stage             # 搜索模式: two_stage / function_call
AIGF_SEARCH_API=tavily                 # 搜索API: tavily / duckduckgo / bing
AIGF_SEARCH_API_KEY=""                 # 搜索 API Key（tavily/bing 必填，duckduckgo 无需）
AIGF_SEARCH_MAX_RESULTS=3              # 最大搜索结果数
```

#### 原有可选配置

```env
# --- 基础 ---
AIGF_MEME_ENABLED=true                 # 是否启用表情包功能（默认 true）
AIGF_MEME_MAX_COUNT=200                # 自动收集的表情包最大数量（默认 200）
AIGF_DEFAULT_PRESET=default            # 默认预设名称（默认 "default"）

# --- 请求控制 ---
AIGF_BATCH_COUNT=10                    # 攒满多少条消息后触发 LLM 请求（默认 10）
AIGF_BATCH_TIMEOUT=30.0                # 距最后一条消息多少秒后触发（默认 30.0）
AIGF_RECENT_MESSAGES=15                # prompt 中包含的最近历史消息条数（默认 15）

# --- 代理 ---
AIGF_PROXY_ENABLED=false               # 是否启用代理（默认 false）
AIGF_HTTP_PROXY="http://127.0.0.1:7890"
AIGF_HTTPS_PROXY="http://127.0.0.1:7890"

# --- 图片理解（VLM） ---
AIGF_IMAGE_MODE="vlm"                  # vlm=独立VLM分析, llm=LLM直接看图
AIGF_VLM_ENABLED=true                  # 是否启用VLM（默认 true）
AIGF_VLM_MODEL="qwen3.6-plus"         # VLM 模型名称
AIGF_VLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
AIGF_VLM_API_KEY=""                    # 为空时使用 chat key
```

## 命令

| 命令 | 说明 | 权限 |
|------|------|------|
| `status` / `状态` | 查看机器人状态（角色、社交能量、最近消息） | SUPERUSER |
| `set_role <名字> <设定>` | 设置机器人角色 | SUPERUSER |
| `reset` / `重置` | 重置会话（清空所有记忆） | SUPERUSER |
| `presets` | 查看可用的角色预设 | SUPERUSER |
| `set_preset <预设名>` | 加载指定的角色预设 | SUPERUSER |
| `reload_meme` / `重载表情包` | 热重载表情包配置 | SUPERUSER |

## 触发机制

- 攒够 **10 条**新消息，或最后一条消息后 **30 秒**内无新消息，触发一次处理
- 若超时触发时检测到同一用户在连续发送（间隔 < `AIGF_MERGE_WINDOW`），自动等待下一周期
- 消息合并窗口内的同一用户连续消息会被合并为一条展示给 LLM

## 记忆系统

四层记忆由 LLM 自主管理：

### 短期记忆
对话摘要、临时上下文，LLM 可增删改。按群隔离存储。

### 长期记忆
重要事件、知识，LLM 可增删改。按群隔离存储。

### 群友信息
每个群友一个 JSON 文件，全局共享。包含昵称、别名、曾用昵称、个人信息、所在群列表。

### 文化记忆（Beta 新增）
梗、网络用语、流行语。LLM 主动学习和存储，根据聊天内容自动匹配。

## 与 v0.3.2 的区别

| 特性 | v0.3.2 | 0.4.0-beta |
|------|--------|------------|
| 回复风格 | 较正式，长度固定 | 口语化，长度有变化 |
| 回复决策 | 硬编码规则 | 社交能量 + 兴趣驱动 |
| 消息处理 | 逐条展示 | 连续消息自动合并 |
| 触发时机 | 固定超时 | 智能延迟（等待连续发送完成） |
| 社交状态 | 无 | 动态社交能量系统 |
| 联网搜索 | 无 | 支持 Tavily / DuckDuckGo |
| 文化记忆 | 无 | 自动学习和匹配梗/网络用语 |
| 架构 | 单次 LLM 调用 | 单次 LLM 调用（搜索时可能两次） |

## 依赖

```
必需：nonebot2, nonebot-adapter-onebot, nonebot-plugin-localstore,
     openai, httpx, anyio, pillow, pydantic, numpy
可选：tavily-python（Tavily 搜索）、duckduckgo-search（DuckDuckGo 搜索）
     Bing 搜索使用 httpx（已在必需依赖中），无需额外安装
```

## 一些碎碎念
- 本项目移除了原插件的 HippoRAG 和情绪系统，拟人程度远不如原插件
- 本项目的token消耗理论上相较原插件能减少约30-50%，但绝对值仍不低，每次请求约消耗 20K tokens，在记忆数据丰富之后会更高
- 推荐使用价格较为低廉的模型作为llm模型（群友就是要笨笨的才可爱呀），再以识图能力较好的vlm模型作为辅助（要是看不懂表情包还是会比较尴尬的）
