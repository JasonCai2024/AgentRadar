# AgentRadar (智能体状态雷达)

<p align="center">
  <img src="assets/icon.ico" width="80" height="80" alt="AgentRadar Logo">
</p>

<p align="center">
  <a href="https://github.com/JasonCai2024/AgentRadar/releases"><img src="https://img.shields.io/badge/Release-v0.5.4-blue.svg" alt="Release"></a>
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?logo=windows&logoColor=white" alt="Platform Windows">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License MIT"></a>
</p>

> 🚀 **专为 Windows 平台多 GUI 智能体打造的轻量级工作状态监控与一键切窗 HUD**  
> 实时穿透感知 **Google AntiGravity**、**Qoder (Qcode)**、**MiniMax Code**、**OpenAI Codex**、**WorkBuddy** 的会话级运行负荷、思考状态与待审批弹窗。

---

## 🌟 为什么需要 AgentRadar？

在现代日常开发中，许多开发者习惯在 Windows 下**同时打开多个独立的 GUI 智能体客户端**：
* 有的在用 **Google AntiGravity** 做全局架构与方案设计；
* 有的在用 **Qoder (Qcode)** 编写核心业务代码；
* 有的在用 **MiniMax Code** 做特定模块的并发编码；
* 有的在用 **OpenAI Codex** 进行逻辑审计与代码审查；
* 有的在用 **WorkBuddy** 处理项目协作与特定任务流。

### 核心痛点
开发者不需要一个“大而全”的第三方统一界面强行取代各个原生客户端（因为每个客户端在 Windows 任务栏都有独立的图标、快捷键与编辑器特色），但面临两个极其尴尬的困扰：
1. **黑盒运行，盲目切换**：不知道切过去时 AI 是在“正在写代码”、“深度思考中”，还是已经“任务结束很久了”；
2. **卡住无感知**：AI 在执行某条终端命令或敏感文件读写时，常常会停下来**“等待用户确认/审批（Pending Approval）”**。由于没有全局通知，开发者往往让它干耗了十几分钟才发现，白白浪费时间。

**AgentRadar** 正是为此而生：**作为操作系统的“旁路雷达”，只做状态感知与快捷置顶，完全不侵入、不改变你原有的任何开发工作流！**

---

## 🎯 核心功能特性

### 1. Windows 系统托盘状态灯（Tray Indicator）
* 常驻在 Windows 任务栏右下角托盘区，用一颗极简的小图标向你汇报全局状态：
  * ⚪ **灰色**：所有智能体均未启动（Offline）；
  * 🔵 **蓝色**：智能体已启动并就绪（Idle），等待用户输入；
  * 🟢 **绿色**：至少有一个智能体正在推理思考、编写代码或执行构建（Thinking / Working）；
  * 🟡 **黄色**：**有智能体正在等待用户授权/按回车确认（Pending Approval）！**

### 2. 托盘聚合工作看板（Tray HUD Card）
左键点击托盘图标或双击桌面快捷方式，瞬时弹出一个高对比度深色微型看板（`#0f172a`）：
* **💬 细粒度单会话独立成行（一行显示一个会话，完全消灭状态混淆）**：
  * 直接读取底层数据库（SQLite / JSONL）与真实会话转录流水（Transcript / Rollout）；
  * **AntiGravity 独立分行**：多个活跃会话分行展示（如一行显示 `并购贷后管理`，另一行显示 `Clone T3 Code Project`），各自拥有完全独立的状态指示（一个工作中，一个就绪），消灭粗暴聚合与状态串扰；
  * **OpenAI Codex 独立分行**：并发多线程分别成行（如 `任务架构设计` 与 `3-0`）；
  * **MiniMax Code 穿透监测**：精准直连本地运行时数据库识别活跃任务与 `started` 工作态；
  * **Qoder 穿透监测与实时工作态捕获**：解析最新 JSONL Turn 消息流，精准捕获正在调用工具（`tool_use`）与流式生成的忙碌状态；
  * **WorkBuddy 动态感知**：读取 `workbuddy.db` 状态与心跳日志，多任务动态挂载。
* **纯图元极简单行布局（宽度仅 340px，占用屏幕空间缩减 >60%）**：
  * **单行排布**：`[⠿ 移动手柄]` `[状态灯 (⚪/🔵/🟢/🟡)]` `[智能体名称]` `[会话名称]` (弹性拉伸) `[结束时间 (仅待命态)]` `[✕ 隐藏会话]`；
  * **彻底剔除右侧冗余文字**：去除“工作中 25s”、“就绪”等文字胶囊，纯靠直观的状态指示灯（🟢 工作中 / 🔵 待命 / ⚪ 离线 / 🟡 等待确认）区分，界面极度清爽；
  * **待命完成时间展示**：当会话完成工作转为待命（🔵）后，自动在右侧叉号左侧呈现最新完成时间（`HH:MM`），活跃中自动隐藏；
  * **鼠标悬停浮动气泡**：运行秒数、详细状态与操作提示全部收录在 Tooltip 中，鼠标滑过即可查看；
* **极简动态生命周期模型**：
  * **活跃自动追加**：任何已配置的智能体产生新活跃会话时，自动在看板末尾追加新行；
  * **手动快速隐藏（✕）**：待命状态的非关注会话随时可点右侧 `✕` 移除隐藏；
  * **智能唤醒复位**：已被隐藏的会话一旦重新被激活开始工作，系统自动解除隐藏并重新展示；
  * **左侧拖拽排序**：鼠标按住左侧 `⠿` 手柄，可上下拖拽任意调整会话卡片优先显示次序。
* **点击一键切窗**：在任意会话卡片上单击，瞬间将对应的客户端窗口激活并置顶到屏幕最前。

### 3. 三重混合状态感知引擎（Hybrid Sensing Engine）
针对“大模型深度思考时文件大小不改变”的技术难题，AgentRadar 综合三大探针：
* **探针 A (Process Probe)**：单次快照追踪进程树与多核 CPU 计算负荷（系统开销 <1.0%）；
* **探针 B (Network Probe)**：嗅探目标进程树指向大模型 API 端点（HTTPS 443）的活跃 TCP 连接；
* **探针 C (Log Probe & Session Resolver)**：64KB 逆向安全读取最新转录流水与 SQLite 库，毫秒级捕获工具调用与待审批模式。

### 4. 彻底解决 Windows 前台窗口激活限制
使用 Win32 `AttachThreadInput` + `SetForegroundWindow` + `VK_MENU` 模拟机制，即使 AgentRadar 作为后台托盘运行，也能在用户点击时**瞬间将最小化或失焦的客户端拉到屏幕最前方**！

---

## 🖥️ 目标支持的 5 大 GUI 智能体全景

| 智能体框架 | 进程标识 | 本地数据 / 日志目录 | 核心工作场景 |
| :--- | :--- | :--- | :--- |
| **Google AntiGravity** | `Antigravity.exe` | `AppData/Roaming/Antigravity`、`~/.gemini/` | 架构设计、全局规划与长上下文理解 |
| **Qoder (Qcode)** | `Qoder.exe` | `AppData/Roaming/qoder`、`com.qoder.app.stable` | 全栈代码补全与业务逻辑实现 |
| **MiniMax Code** | `MiniMax Code.exe` | `AppData/Roaming/MiniMax Agent`、`MiniMax` | 专项模块生成、MiniMax 系列模型编码 |
| **OpenAI Codex** | `ChatGPT.exe`、`codex.exe` | `AppData/Roaming/Codex`、`~/.codex/` | 严密逻辑审计、代码审查与单元测试 |
| **WorkBuddy** | `WorkBuddy.exe` | `AppData/Roaming/WorkBuddy`、`~/.workbuddy/` | 任务协作、项目流转协同处理 |

---

## 📦 获取与安装

### 方式 A：直接下载开箱即用版（推荐终端用户）
直接前往 [GitHub Releases](https://github.com/JasonCai2024/AgentRadar/releases) 下载最新发布的单文件绿色版：
- 下载 `AgentRadar.exe`，免安装、解压即用；
- 双击即可在系统托盘静默启动。

### 方式 B：从源码运行（推荐开发者）

#### 1. 克隆代码仓库
```bash
git clone https://github.com/JasonCai2024/AgentRadar.git
cd AgentRadar
```

#### 2. 安装依赖
```bash
pip install -r requirements.txt
```

#### 3. 运行方式
- **静默后台启动（推荐日常使用）**：
  - 双击运行根目录下的 [`run.bat`](./run.bat)
  - 启动后小图标常驻在右下角系统托盘，左键点击图标随时唤出 HUD 看板。
- **控制台调试模式（查看实时感知日志）**：
  - 双击运行根目录下的 [`run_console.bat`](./run_console.bat)
- **生成桌面快捷方式**：
  - 运行 `python scripts/create_shortcut.py`，即可在桌面生成带专属雷达图标的快捷方式。

---

## 🛠️ 打包为单一可执行文件 (.exe)

项目内内置了经过严格优化的 PyInstaller 一键打包脚本：
```bash
# 方式一：直接双击运行根目录下的 build.bat
build.bat

# 方式二：命令行执行
python scripts/build_exe.py
```
构建成功后，将在 `dist/` 目录下生成绿色独立的 `AgentRadar.exe`。

---

## 📂 项目结构规范

```text
AgentRadar/
├── assets/                     # 资源文件 (图标 icon.ico 等)
├── docs/                       # 项目文档
│   ├── DESIGN.md               # 🌟 系统详细设计与技术规格说明书
│   ├── CHANGELOG.md            # 📜 完整版本演进与优化记录
│   └── issue_log.md            # 历史性能专项调优与故障排查记录
├── scripts/                    # 运维与打包辅助脚本
│   ├── build_exe.py            # PyInstaller 单文件打包脚本
│   ├── create_shortcut.py      # 一键创建桌面快捷方式
│   ├── check_minimax_session.py
│   ├── check_qoder_db.py
│   └── diagnose_feedback.py
├── src/                        # 源代码目录
│   ├── adapters/               # 针对 5 大 GUI 智能体的专用特征定义
│   │   ├── antigravity.py      # Google AntiGravity 适配器
│   │   ├── qoder.py            # Qoder 适配器
│   │   ├── minimax_code.py     # MiniMax Code 适配器
│   │   ├── codex.py            # OpenAI Codex 适配器
│   │   └── workbuddy.py        # WorkBuddy 适配器
│   ├── core/                   # 核心感知引擎
│   │   ├── engine.py           # 核心有限状态机与信号调度中心
│   │   ├── process_probe.py    # 全局单快照进程树扫描与 CPU 追踪
│   │   ├── network_probe.py    # TCP Socket 与 HTTPS 连接嗅探
│   │   ├── log_probe.py        # 日志探测
│   │   └── session_resolver.py # 穿透级多会话解析器 (SQLite/JSONL 64KB流式反向解析)
│   ├── win32/                  # Windows API 穿透与窗口激活
│   │   └── window_manager.py   # HWND 定位与 AttachThreadInput 置顶穿透
│   └── ui/                     # 任务栏托盘与弹出卡片
│       ├── hud_card.py         # 深板岩色状态 HUD 看板 (支持无感知拖拽排序与单会话移除)
│       └── tray_app.py         # 动态雷达托盘图标绘制与右键菜单
├── .gitignore                  # Git 忽略文件规则
├── build.bat                   # 一键打包单文件可执行程序
├── LICENSE                     # MIT 开源许可证
├── order_config.json.example   # 看板布局配置示例模板
├── README.md                   # 项目总体使用说明书
├── requirements.txt            # 项目 Python 依赖清单
├── run.bat                     # 一键后台启动批处理
└── run_console.bat             # 一键调试启动批处理
```

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 协议开源。
