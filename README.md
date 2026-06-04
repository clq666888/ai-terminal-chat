# DeepSeek API 命令行对话工具

基于 OpenAI 兼容接口的命令行 AI 对话工具，支持多智能体、工具调用、MCP 扩展和流式输出。

## 快速开始

1. 打开 `agents/global.txt`，填写 API Key、服务商、模型
2. 运行：

```bash
python3 start.py
```

## 命令列表

| 命令 | 说明 |
|------|------|
| `/exit` | 退出 |
| `/clear` | 清空记忆 |
| `/undo` | 撤销上一轮 |
| `/compress` | 压缩历史（减少 token） |
| `/reload` | 热重载配置和智能体 |
| `/agents` | 查看智能体列表 |
| `/mcp` | 查看已加载的 MCP 工具 |
| `@名称` | 切换智能体 |
| `@名称 消息` | 切换并直接对话 |
| `"""` | 多行输入模式 |

## 内置工具

AI 可以主动调用以下工具：

| 工具 | 功能 |
|------|------|
| `read_file` | 读取文件 |
| `edit_file` | 写入/创建/删除文件 |
| `run_command` | 执行命令 |
| `list_dir` | 列出目录 |
| `search_files` | 搜索文本 |
| `call_agent` | 调用其他智能体 |
| `ask_user` | 向用户提问 |

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

## 配置文件

`config.txt` 中可调整运行参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 最大记忆轮数 | 50 | 超出后自动丢弃早期对话 |
| 最大工具调用轮数 | 20 | 单次对话最多调用工具次数 |
| 连接超时秒数 | 10 | API 连接超时 |
| 响应超时秒数 | 120 | API 响应超时 |
| 历史压缩阈值轮数 | 30 | 自动触发压缩的轮数 |
| 压缩保留最近轮数 | 5 | 压缩后保留的最近对话轮数 |

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

## 项目结构

```
api调用脚本/
├── start.py              # 入口（自动检测系统）
├── config.txt            # 运行参数
├── config_manager.py     # 配置解析
├── agents/               # 智能体配置
│   ├── global.txt        # 全局配置（必填）
│   └── *.txt             # 自定义智能体
├── mcp/                  # MCP 扩展
│   ├── mcp_client.py     # MCP 通信核心
│   └── servers/          # MCP 配置文件（.json）
├── linux/                # Linux/macOS 版本
│   ├── api_chat.py       # 主入口
│   ├── chat_core.py      # API 请求与历史管理
│   ├── tools.py          # 工具定义与执行
│   ├── terminal_control.py
│   └── agent_manager.py
└── windows/              # Windows 版本
    ├── api_chat.py
    ├── chat_core.py
    ├── tools.py
    ├── terminal_control.py
    └── agent_manager.py
```

## 环境要求

- Python 3.7+
- `requests` 库（`pip install requests`）
- Node.js（仅使用 MCP 时需要）
