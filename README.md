# PolyAI Chat — Web 端多模型 AI 对话工具

一个基于 Flask 的 Web AI 对话工具，支持多对话管理、多模型切换、自定义智能体，兼容所有 OpenAI Chat Completions API 格式的服务。

> 本分支 (`PolyAI-Chat`) 专注于 Web 端，终端版（Linux/Windows）请切换到 `PolyAI-CLI` 分支。

## 项目结构

```
api调用脚本/
├── web/
│   ├── app.py                  # Flask 后端 + API 路由 + 配置区
│   ├── chat_core.py            # 公共核心（API 请求、流式解析、历史管理）
│   ├── templates/
│   │   └── index.html          # 聊天页面
│   ├── static/
│   │   ├── style.css           # 深色主题样式
│   │   ├── app.js              # 前端交互逻辑
│   │   └── uploads/            # 智能体头像上传目录
│   ├── settings.json           # 运行时配置持久化（自动生成，已 gitignore）
│   └── agents.json             # 智能体配置持久化（自动生成，已 gitignore）
├── 提示词/                     # 系统提示词文件目录
│   └── 无限制.txt
├── .gitignore
└── README.md
```

## 前置条件

- Python 3.8+
- `requests` 库
- `flask` 库
- 一个 API Key 文件（纯文本，内容只有 Key 本身）

```bash
pip install requests flask
```

## 快速启动

```bash
cd web
python3 app.py
```

启动后访问 `http://localhost:8080`，局域网设备访问 `http://你的IP:8080`。

## 功能

### 多对话管理
- 侧边栏创建、切换、删除对话
- 每个对话独立维护历史记录
- 对话标题可编辑

### 多模型支持

内置以下服务商和模型：

| 服务商 | 默认模型 |
|--------|----------|
| DeepSeek | deepseek-chat, deepseek-reasoner, deepseek-v4-pro, deepseek-v4-flash |
| OpenAI | gpt-4o, gpt-4o-mini, gpt-3.5-turbo |
| 通义千问 | qwen-turbo, qwen-plus, qwen-max |
| 豆包 | doubao-1.5-pro-32k, doubao-1.5-lite-32k |
| Gemini | gemini-2.0-flash, gemini-2.5-pro |
| Grok | grok-3, grok-3-mini |
| Claude | claude-sonnet-4-20250514, claude-3-5-sonnet-20241022 |
| 零一万物 | yi-lightning |

- 设置面板中可切换服务商、模型、API Key、接口地址
- 输入框下方模型快速切换栏
- 支持添加自定义模型名称

### 自定义智能体
- 输入框上方智能体选择器（下拉菜单）
- 每个智能体可配置：名称、头像、系统提示词、绑定模型
- 智能体管理面板支持新建、编辑、删除
- 切换智能体实时生效，系统提示词即时更换
- 不选择智能体时为通用模式（无系统提示词）

### 其他
- 深色主题界面
- 流式输出（SSE），AI 回复逐字显示
- Enter 发送，Shift+Enter 换行
- Markdown 渲染
- 清空记忆按钮
- 响应式布局，支持移动端
- 配置自动持久化到 settings.json

## 配置说明

首次启动时 `app.py` 顶部配置区提供默认值：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `BASE_URL` | API 接口地址 | `https://api.deepseek.com/v1/chat/completions` |
| `KEY_FILE_PATH` | API Key 文件路径 | `/home/sti/apikey.txt` |
| `MODEL` | 默认模型 | `deepseek-chat` |
| `MAX_HISTORY_ROUNDS` | 上下文轮数（0 = 不限） | `50` |
| `PORT` | 监听端口 | `8080` |

启动后可通过网页右上角设置面板在线修改，无需重启。

## 注意事项

- API Key 文件不要提交到 Git
- settings.json 和 agents.json 已在 .gitignore 中排除
- Flask 开发服务器适合个人使用，不建议暴露到公网
- `MAX_HISTORY_ROUNDS` 建议设为 20-50，防止 token 消耗过大
