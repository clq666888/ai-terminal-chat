# PolyAI-CLI

命令行 AI 对话工具，支持多智能体、工具调用、MCP 扩展和流式输出。

## 快速开始

1. 打开 `agents/global.txt`，填写 API Key、服务商、模型
2. 运行：

```bash
python3 start.py
```

### ⚠️ Windows 用户注意

如果 Windows 下运行 `py start.py` 无法正常启动，请改用以下命令：

```bash
python -u start.py
```

## 功能一览

- **多智能体** — 创建不同角色的 AI，用 `@名称` 随时切换
- **工具调用** — AI 可以读写文件、执行命令、搜索代码
- **MCP 扩展** — 接入社区工具（长期记忆、网络搜索等）
- **会话持久化** — 保存/恢复对话，退出自动存档
- **权限控制** — 4 级权限，从纯聊天到全自动
- **流式输出** — 实时显示 AI 回复，Ctrl+Q 随时中断

## 常用操作

| 你想做什么 | 怎么做 |
|-----------|--------|
| 清空对话重新开始 | 输入 `/clear` |
| 撤回最近的对话 | 输入 `/undo` |
| 保存当前会话 | 输入 `/save` 或 `/save 名称` |
| 恢复之前的会话 | 输入 `/load 名称` |
| 切换智能体 | 输入 `@标识名`，如 `@coder` |
| 切换并直接对话 | 输入 `@coder 帮我写个函数` |
| 中断 AI 生成 | 按 `Ctrl+Q` |
| 修改配置后生效 | 输入 `/reload` |
| 查看 AI 改了哪些文件 | 输入 `/diff` |
| 多行输入 | 输入 `"""` 开始，再输入 `"""` 结束 |

> 完整指令说明见 [指令操作指南.md](指令操作指南.md)

## 智能体

在 `agents/` 目录下创建 `.txt` 文件即可添加智能体，留空的字段自动继承 `global.txt`。

```
[名称]
开发工程师
[标识名]
coder
[系统提示词]
你是一个专业的开发工程师。
[可用工具]
read_file, edit_file, run_command, list_dir, search_files
[可被调用]
是
[何时调用]
当需要写代码或修改文件时调用
```

- 创建方法详见 `agents/创建智能体须知.md`
- 提示词写法详见 `agents/提示词编写指南.md`
- 自定义智能体的 `.txt` 文件不会提交到仓库

## 权限等级

`config.txt` 中的 `[权限]` 字段控制 AI 可使用的工具范围：

| 等级 | 说明 |
|------|------|
| 0 | 仅聊天，不使用任何工具 |
| 1 | 只读（查看文件、目录、搜索） |
| 2 | 读写，文件修改和命令执行需确认 |
| 3 | 完全自动（默认） |

## MCP 扩展

MCP 让你的 AI 能调用外部能力（长期记忆、网络搜索、数据库等）。

**安装示例（长期记忆）：**

```bash
sudo npm install -g @modelcontextprotocol/server-memory
echo '{"command": "npx", "args": ["@modelcontextprotocol/server-memory"]}' > mcp/servers/memory.json
```

启动后自动加载，输入 `/mcp` 查看。

**配置格式：** `mcp/servers/` 下每个 `.json` 对应一个 MCP Server：

```json
{"command": "启动命令", "args": ["参数1", "参数2"]}
```

**找更多 MCP Server：** [mcphub.io](https://mcphub.io) · [mcp.so](https://mcp.so)

> 没有配置 MCP 时工具正常运行，无任何影响。

## 配置文件

`config.txt` 可调整运行参数，修改后输入 `/reload` 立即生效：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 最大记忆轮数 | 50 | 超出后自动丢弃早期对话 |
| 最大工具调用轮数 | 50 | 单次对话最多调用工具次数 |
| 连接超时秒数 | 10 | API 连接超时 |
| 响应超时秒数 | 120 | API 响应超时 |
| 历史压缩阈值轮数 | 30 | 自动触发压缩的轮数 |
| 压缩保留最近轮数 | 10 | 压缩后保留的最近对话轮数 |
| diff保存最大轮数 | 10 | AI 文件改动记录保留的轮数 |
| 权限 | 3 | 工具权限等级（0-3） |

## 支持的服务商

| 服务商 | 填写值 |
|--------|--------|
| DeepSeek | `deepseek` |
| OpenAI | `openai` |
| 月之暗面 | `moonshot` |
| 智谱 | `zhipu` |
| 通义千问 | `qwen` |
| 自定义 | 在 `[API地址]` 填完整 URL |

## 项目级上下文

在任意工作目录下创建 `.polyai-context` 文件，内容会自动注入到系统提示词中：

```
[项目说明]
这是一个 Python Web 项目，使用 FastAPI 框架

[代码规范]
使用 4 空格缩进，变量名用 snake_case
```

## 项目结构

```
├── start.py              # 入口
├── config.txt            # 运行参数
├── 指令操作指南.md        # 指令详细说明
├── agents/               # 智能体配置
│   ├── global.txt        # 全局配置（必填）
│   ├── 创建智能体须知.md  # 智能体创建说明
│   ├── 提示词编写指南.md  # 提示词编写教程
│   └── *.txt             # 自定义智能体（不提交到仓库）
├── 提示词/               # 可选的提示词模板
├── core/                 # 核心代码（跨平台统一）
├── mcp/servers/          # MCP 配置文件（.json）
└── sessions/             # 会话存档（不提交内容）
```

## 环境要求

- Python 3.7+
- `requests` 库（`pip install requests`）
- Node.js（仅使用 MCP 时需要）
