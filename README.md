# DeepSeek API 命令行对话工具

基于 OpenAI 兼容接口的命令行 AI 对话工具，支持多智能体、工具调用、MCP 扩展和流式输出。

## 快速开始

1. 打开 `agents/global.txt`，填写 API Key、服务商、模型
2. 运行：

```bash
python3 start.py
```

> Windows 如果无法正常启动，请使用 `python -u start.py`

## 命令列表

| 命令 | 说明 |
|------|------|
| `/exit` | 退出 |
| `/clear` | 清空记忆 |
| `/undo [N]` | 回退到第 N 轮（默认回退1轮） |
| `/compress` | 压缩历史（减少 token） |
| `/reload` | 热重载配置和智能体 |
| `/agents` | 查看智能体列表 |
| `/diff` | 查看 AI 的文件改动记录 |
| `/mcp` | 查看已加载的 MCP 工具 |
| `/save [名]` | 保存当前会话 |
| `/load <名>` | 恢复已保存的会话 |
| `/sessions` | 查看所有已保存会话 |
| `/list` | 显示所有指令 |
| `@名称` | 切换智能体 |
| `@名称 消息` | 切换并直接对话 |
| `"""` | 多行输入模式 |
| `Ctrl+Q` | 中断 AI 生成或工具执行 |

## 权限等级

通过 `config.txt` 的 `[权限]` 字段控制 AI 可使用的工具范围：

| 等级 | 说明 |
|------|------|
| 0 | 仅聊天，不允许使用任何工具 |
| 1 | 只读（read_file、list_dir、search_files、ask_user） |
| 2 | 读写，文件修改和命令执行需用户确认 |
| 3 | 完全自动，所有工具无需确认（默认） |

## 内置工具

AI 可以主动调用以下工具：

| 工具 | 功能 |
|------|------|
| `read_file` | 读取文件 |
| `edit_file` | 写入/创建/删除文件 |
| `run_command` | 执行命令 |
| `list_dir` | 列出目录（支持过滤隐藏文件） |
| `search_files` | 搜索文本（支持过滤隐藏文件） |
| `call_agent` | 调用其他智能体 |
| `ask_user` | 向用户提问 |
| `get_diff` | 查看本次会话中 AI 的文件改动记录 |

## MCP 扩展

MCP（Model Context Protocol）让你的工具能调用社区提供的外部能力，比如长期记忆、网络搜索、数据库操作等。

### 安装一个 MCP Server

以 memory（长期记忆）为例：

```bash
# 第一步：安装
sudo npm install -g @modelcontextprotocol/server-memory

# 第二步：创建配置文件
echo '{"command": "npx", "args": ["@modelcontextprotocol/server-memory"]}' > mcp/servers/memory.json
```

启动工具后自动加载，输入 `/mcp` 可查看已加载的工具。

### 配置格式

`mcp/servers/` 目录下每个 `.json` 文件对应一个 MCP Server：

```json
{"command": "启动命令", "args": ["参数1", "参数2"]}
```

常见例子：

```json
{"command": "npx", "args": ["@modelcontextprotocol/server-memory"]}
{"command": "npx", "args": ["@modelcontextprotocol/server-brave-search"]}
{"command": "python", "args": ["-m", "mcp_server_sqlite", "--db-path", "./data.db"]}
```

### 去哪找 MCP Server

- npm 包：`npm install -g @xxx/server-xxx`
- Python 包：`pip install mcp-server-xxx`
- 社区目录：https://mcphub.io 、https://mcp.so

### 说明

- 没有配置任何 MCP 时，工具正常运行，无影响
- MCP 工具对所有智能体默认可用
- `mcp/servers/*.json` 已加入 `.gitignore`，不会提交到仓库
- 别人 clone 后需自行安装和配置所需的 MCP Server

## 多智能体

在 `agents/` 目录下创建 `.txt` 文件即可添加智能体：

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

留空的字段自动继承 `global.txt`。详见 `agents/创建智能体须知.md`。

> 注意：`agents/` 目录下除 `global.txt` 和 `创建智能体须知.md` 外的 `.txt` 文件均不会提交到仓库（已通过 `.gitignore` 忽略），每个用户可自由创建自己的智能体而不影响他人。

## 配置文件

`config.txt` 中可调整运行参数：

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

修改后输入 `/reload` 立即生效。

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

在任意工作目录下创建 `.polyai-context` 文件，内容会自动注入到系统提示词中。格式：

```
[项目说明]
这是一个 Python Web 项目，使用 FastAPI 框架

[代码规范]
使用 4 空格缩进，变量名用 snake_case
```

## 会话持久化

支持保存和恢复对话历史（包括文件改动记录）：

- `/save` 或 `/save 名称` 保存当前会话
- `/load 名称` 恢复会话
- `/sessions` 查看所有已保存会话
- 退出时自动保存为 `autosave`

会话文件存放在 `sessions/` 目录下，不会提交到 git 仓库。

## 项目结构

```
api调用脚本/
├── start.py              # 入口（自动检测系统）
├── config.txt            # 运行参数
├── config_manager.py     # 配置解析
├── 指令操作指南.md        # 所有指令的详细使用说明
├── sessions/             # 会话存档（不提交内容）
├── agents/               # 智能体配置
│   ├── global.txt        # 全局配置（必填）
│   ├── 创建智能体须知.md  # 智能体创建说明
│   └── *.txt             # 自定义智能体（不提交到仓库）
├── mcp/                  # MCP 扩展
│   ├── mcp_client.py     # MCP 通信核心
│   └── servers/          # MCP 配置文件（.json）
├── linux/                # Linux/macOS 版本
│   ├── api_chat.py       # 主入口
│   ├── chat_core.py      # API 请求与历史管理
│   ├── tools.py          # 工具定义与执行
│   ├── terminal_control.py
│   ├── spinner.py        # 思考动画
│   └── agent_manager.py
└── windows/              # Windows 版本
    ├── api_chat.py
    ├── chat_core.py
    ├── tools.py
    ├── terminal_control.py
    ├── spinner.py
    └── agent_manager.py
```

## 环境要求

- Python 3.7+
- `requests` 库（`pip install requests`）
- Node.js（仅使用 MCP 时需要）
