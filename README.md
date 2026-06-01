# PolyAI Chat — Web 端多模型 AI 对话工具

一个基于 Flask 的 Web AI 对话工具，支持多对话管理、多模型切换、自定义智能体、文件上传解析，兼容所有 OpenAI Chat Completions API 格式的服务。

> 本分支 (`PolyAI-Web`) 专注于 Web 端，终端版（Linux/Windows）请切换到 `PolyAI-CLI` 分支。

## 项目结构

```
api调用脚本/
├── web/
│   ├── app.py                  # Flask 后端 + API 路由 + 配置区
│   ├── chat_core.py            # 公共核心（API 请求、流式解析、历史管理）
│   ├── templates/
│   │   └── index.html          # 聊天页面
│   └── static/
│       ├── style.css           # 深色主题样式
│       ├── app.js              # 前端交互逻辑
│       ├── icon.svg            # 图标
│       ├── marked.min.js       # Markdown 渲染库
│       └── uploads/            # 智能体头像上传目录（自动创建）
├── 提示词/                     # 系统提示词文件目录
│   └── 无限制.txt
├── linux_start.sh              # Linux 服务管理脚本（start/stop/restart/status/log）
├── windows_start.bat           # Windows 服务管理脚本（start/stop/restart/status/log）
├── .gitignore
└── README.md
```

以下文件运行时自动生成，已被 `.gitignore` 排除：

| 文件 | 说明 |
|------|------|
| `web/settings.json` | 运行时配置持久化（服务商、模型、Key 路径等） |
| `web/agents.json` | 智能体配置持久化 |
| `web/conversations.json` | 对话历史持久化 |
| `web/.polyai.pid` | 后台进程 PID 文件 |
| `web/.polyai.log` | 后台运行日志 |
| `web/static/uploads/` | 智能体头像上传目录 |

## 前置条件

- Python 3.8+
- `requests` 库
- `flask` 库
- 一个 API Key 文件（纯文本，内容只有 Key 本身）

```bash
pip install requests flask
```

如果需要上传 PDF / Word / Excel 文件并自动解析，还需安装（可选）：

```bash
pip install PyPDF2 python-docx openpyxl
```

## 快速启动

**Linux：**

```bash
bash linux_start.sh          # 启动（默认）
bash linux_start.sh stop     # 关闭
bash linux_start.sh restart  # 重启
bash linux_start.sh status   # 查看运行状态
bash linux_start.sh log      # 查看最近日志
```

脚本以后台进程运行，PID 记录在 `web/.polyai.pid`，日志输出到 `web/.polyai.log`。
启动时若端口已被占用会自动释放；已在运行时不会重复启动。

**Windows：**

双击 `windows_start.bat` 启动，或在命令行中使用：

```cmd
windows_start.bat            # 启动（默认）
windows_start.bat stop       # 关闭
windows_start.bat restart    # 重启
windows_start.bat status     # 查看运行状态
windows_start.bat log        # 查看最近日志
```

**手动启动：**

```bash
cd web
python3 app.py
```

启动后访问 `http://localhost:8080`，局域网设备访问 `http://你的IP:8080`。

## 功能

### 多对话管理
- 侧边栏创建、切换、删除对话
- 每个对话独立维护历史记录
- 对话标题自动生成，支持手动修改
- 对话历史持久化到 `conversations.json`，重启不丢失

### 多模型支持

内置以下服务商和模型：

| 服务商 | 模型 |
|--------|------|
| DeepSeek | deepseek-chat, deepseek-reasoner, deepseek-v4-pro, deepseek-v4-flash |
| OpenAI | gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo, o1, o1-mini, o3-mini |
| Claude | claude-sonnet-4-20250514, claude-3-5-sonnet-20241022, claude-3-haiku, claude-3-opus |
| Google Gemini | gemini-2.5-flash, gemini-2.5-pro, gemini-2.0-flash, gemini-1.5-pro |
| 通义千问 | qwen-max, qwen-plus, qwen-turbo, qwen-long |
| 智谱 GLM | glm-4-plus, glm-4, glm-4-flash, glm-4-long |
| Moonshot / Kimi | moonshot-v1-128k, moonshot-v1-32k, moonshot-v1-8k |
| 自定义 | 任意 OpenAI 兼容接口 |

- 设置面板中可切换服务商、模型、API Key、接口地址
- 输入框下方模型快速切换栏
- 支持添加、编辑、删除自定义模型

### 自定义智能体
- 输入框上方智能体选择器
- 每个智能体可配置：名称、头像、系统提示词、绑定模型和服务商
- 智能体管理面板支持新建、编辑、删除、上传头像
- 切换智能体实时生效，系统提示词即时更换
- 不选择智能体时为通用模式（无系统提示词）

### 智能体互调
- 智能体可设为「可调用」，配置英文标识名和调用说明
- 主智能体在回复中使用 `[CALL:标识名]...[/CALL]` 自动调用子智能体
- 子智能体独立发起 API 请求，结果自动回填到主回复中

### 文件上传
- 支持上传文件并自动提取文本内容作为对话上下文
- 支持格式：PDF、Word (.docx)、Excel (.xlsx)、CSV、TXT、Markdown、代码文件等
- 支持图片上传（发送给支持多模态的模型）
- 单次提取上限 10 万字符

### 其他
- 深色主题界面
- 流式输出（SSE），AI 回复逐字显示
- Enter 发送，Shift+Enter 换行
- Markdown 渲染
- 清空记忆按钮
- 重试上一轮对话
- 响应式布局，支持移动端
- 配置自动持久化，重启保留设置

## 配置说明

首次启动时 `app.py` 顶部配置区提供默认值：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `BASE_URL` | API 接口地址 | `https://api.deepseek.com/v1/chat/completions` |
| `KEY_FILE_PATH` | API Key 文件路径 | `/home/sti/apikey.txt` |
| `MODEL` | 默认模型 | `deepseek-chat` |
| `MAX_HISTORY_ROUNDS` | 上下文轮数（0 = 不限） | `50` |
| `PORT` | 监听端口 | `8080` |

启动后可通过网页设置面板在线修改，无需重启。还可配置最大上下文大小 (KB)，超出时自动裁剪早期消息。

## 注意事项

- API Key 文件不要提交到 Git
- `settings.json`、`agents.json`、`conversations.json` 已在 `.gitignore` 中排除
- Flask 开发服务器适合个人使用，不建议暴露到公网
- `MAX_HISTORY_ROUNDS` 建议设为 20–50，防止 token 消耗过大
- 启动脚本启动前若端口被占用会自动释放，不会重复启动已运行的实例
