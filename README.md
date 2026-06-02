# DeepSeek API 命令行对话工具

## ⚠️ 使用前必读

首次运行前，必须先配置全局智能体文件 `agents/global.txt`：

1. 打开 `agents/global.txt`
2. 填写你的 API Key（二选一）：
   - `[API Key]` 下方直接写入密钥
   - `[API Key 文件]` 下方写入存放密钥的文件路径（推荐，更安全）
3. 确认 `[服务商]` 和 `[模型]` 与你使用的服务匹配

未正确配置 `global.txt` 时程序将无法启动。

## 使用方法

### 启动

```bash
python3 start.py
```

`start.py` 会自动检测操作系统，加载 `linux/` 或 `windows/` 下的对应入口。

### 单次调用

```bash
python3 start.py 你的问题
```

直接传入问题，AI 回答后自动退出。

### 对话交互

启动后进入交互模式，支持以下命令：

| 命令 | 说明 |
|------|------|
| `exit` | 退出程序 |
| `clear` | 清空当前智能体的对话记忆 |
| `agents` | 显示所有可用智能体列表 |
| `@标识名` | 切换到指定智能体 |
| `@标识名 消息` | 切换到指定智能体并直接发送消息 |

### 切换智能体

```
你: @coder
🔄 已切换到: 开发工程师 (@coder)

你@coder: 帮我写一个排序函数
```

切换后输入提示符会显示当前智能体标识。

## 项目介绍

基于 DeepSeek API（兼容 OpenAI 接口格式）的命令行 AI 对话工具，支持多智能体切换和 Function Calling 工具调用。

### 核心能力

- **多智能体**：通过 `agents/` 目录下的 `.txt` 配置文件定义多个智能体，每个智能体拥有独立的系统提示词、模型、温度、工具权限和对话记忆
- **工具调用**：AI 可以主动操作文件系统，包括读取文件、编辑文件、执行命令、列出目录、搜索文件
- **全局继承**：`global.txt` 是全局默认配置，其他智能体未填写的字段自动继承全局值
- **跨平台**：Linux/macOS 和 Windows 分别适配，各自使用原生终端控制方式

### 内置工具

| 工具 | 功能 |
|------|------|
| `read_file` | 读取文件内容，支持行号范围 |
| `edit_file` | 写入/创建/覆盖/删除文件 |
| `run_command` | 执行 shell 命令 |
| `list_dir` | 列出目录结构 |
| `search_files` | 在文件中搜索文本 |

### 支持的服务商

在 `[服务商]` 字段中填写名称即可自动匹配 API 地址：

| 服务商 | API 地址 |
|--------|----------|
| `deepseek` | https://api.deepseek.com |
| `openai` | https://api.openai.com/v1 |
| `claude` | https://api.anthropic.com/v1 |
| `moonshot` | https://api.moonshot.cn/v1 |
| `zhipu` | https://open.bigmodel.cn/api/paas/v4 |
| `qwen` | https://dashscope.aliyuncs.com/compatible-mode/v1 |

也可以在 `[API地址]` 中直接填写自定义地址。

## 项目结构

```
api调用脚本/
├── start.py                  # 入口，自动检测系统并加载对应版本
├── agents/                   # 智能体配置目录
│   ├── global.txt            # 全局智能体（必须配置）
│   ├── coder.txt             # 开发工程师
│   ├── code-reviewer.txt     # 代码审查员
│   └── 创建智能体须知.md      # 智能体配置格式说明
├── linux/                    # Linux/macOS 版本
│   ├── api_chat.py           # 主入口
│   ├── chat_core.py          # API 请求、history 管理
│   ├── tools.py              # 工具定义与执行
│   ├── terminal_control.py   # 终端控制（termios/tty/select）
│   └── agent_manager.py      # 智能体配置解析
└── windows/                  # Windows 版本
    ├── api_chat.py           # 主入口
    ├── chat_core.py          # API 请求、history 管理
    ├── tools.py              # 工具定义与执行
    ├── terminal_control.py   # 终端控制（msvcrt）
    └── agent_manager.py      # 智能体配置解析
```

## 创建自定义智能体

在 `agents/` 目录下新建 `.txt` 文件，使用 `[字段名]` 格式定义配置：

```
[名称]
我的助手
[标识名]
my-agent
[系统提示词]
你是一个专注于某个领域的助手。
[服务商]
[API地址]
[API Key]
[模型]
[温度]
0.7
[可用工具]
read_file, edit_file
[可被调用]
是
[何时调用]
当需要某种帮助时调用
```

留空的字段会自动继承 `global.txt` 的值。详细说明见 `agents/创建智能体须知.md`。

## 环境要求

- Python 3.7+
- `requests` 库

```bash
pip install requests
```
