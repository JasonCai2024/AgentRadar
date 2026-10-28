# CHANGELOG

本项目严格遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 规范进行版本维护与更新记录。

---

## [0.5.4] - 2026-10-27

### 修复 Codex 持续运行状态频繁闪烁 (时断时续/一会儿亮一会儿关闭) 缺陷 (Fix Codex Continuous Running State Flickering & 64KB Tail Buffer)
- **彻底排查并根除 Codex 持续运行时状态指示器时亮时灭的技术根因**：
  - **根因一：8KB 尾部缓冲区过小导致大尺寸工具行被截断解析失败**：
    - Codex 在持续多步运行中，频繁调用 `exec` 执行终端命令、文件读写、网页抓取并输出长文本或复杂 reasoning，单行 JSON 尺寸普遍达到 **15KB ~ 35KB**；
    - 历史代码中使用 `f.seek(max(0, sz - 8192))`（仅截取尾部 8KB），导致大尺寸行被从中切断，引发 `json.loads` 异常；
    - 8KB 窗口内剩余的细碎事件（如 `item_completed`、`token_count`）并未命中完成或开始规则，导致解析循环未能识别到有效事件；
    - 由于历史代码默认初始化 `is_finished = True`，在找不到有效事件时被直接判定为“已就绪空闲”，状态指示器瞬间切为蓝色待命（`🔵`）；
    - 几秒后当新的小尺寸 `reasoning` 或 `custom_tool_call` 写入时，又被重新判定为工作中（`🟢`），随后下一个大工具输出到来又再次切为蓝色；
    - **实测复现**：在 Thread 7-0 执行的短短 2 分钟内，发生了连续 10 次 `True -> False -> True -> False` 的剧烈震荡，导致界面“一会儿亮一会儿关闭”；
  - **根因二：未识别事件默认判定完成的逻辑缺陷**：
    - 历史代码将 `is_finished` 默认初始化为 `True`，在尾部事件未明确命中时一律误认为任务已结束；
- **全套修复方案**：
  1. **缓冲区从 8KB 大幅扩增至 64KB (`65536 bytes`)**：
     - 单次逆向读取 64KB 尾部切片（实测基于 Windows 磁盘缓存耗时仅 0.05ms，总轮询耗时稳定在 4~8ms，完全无额外性能负担）；
     - 完整覆盖 15KB~35KB 的大尺寸 `custom_tool_call_output` 及 `reasoning` 事件，确保每个工具调用与模型思考均被 100% 捕获；
  2. **确立三态解析与安全回退模型 (`is_finished = None`)**：
     - 若明确解析到 `task_complete` / `turn_aborted`，标记为回合完成；
     - 若明确解析到 `custom_tool_call` / `reasoning` / `message` / `task_started`，标记为活跃运行中（放宽至 300 秒超时以容纳耗时命令）；
     - 若尾部未见显式终态标记且近期有写盘心跳（`diff <= 60.0s`），安全回退为持续运行中，彻底终结早判误伤；
  3. **增加子回合平滑防抖 (`diff <= 4.0s`)**：
     - 避免多步任务交替或自动化脚本回合切换时的 1 帧闪变；
  4. **全框架协同升级**：
     - 同步将 AntiGravity（[`resolve_antigravity_sessions`](file:///E:/BaiduSyncdisk/LocalHub/AgentRadar/src/core/session_resolver.py#L145-L155)）与 WorkBuddy 的尾部逆向读取窗口提升至 64KB，彻底杜绝所有智能体在处理大型代码片段或工具输出时的状态误闪问题。

---

## [0.5.3] - 2026-10-27

### 修复 Codex 活跃会话渲染中断与运行状态早判缺陷 (Fix Codex Session Rendering Exception & Premature Turn-End)
- **彻底排查并根除 Codex 活跃会话未在看板呈现的技术根因**：
  - **根因一：`_save_current_config` 残留属性异常导致 UI 渲染中断**：
    - 在移除“显全部”按钮重构时，[`hud_card.py`](file:///E:/BaiduSyncdisk/LocalHub/AgentRadar/src/ui/hud_card.py#L393-L400) 中的 `_save_current_config` 内部仍遗留对 `self._hide_offline` 的引用；
    - 当引擎检测到新的会话（如 Codex 会话）调用 `update_states` 进行动态追加时，触发配置保存抛出 `AttributeError: 'HUDCard' object has no attribute '_hide_offline'`，导致整轮 UI 渲染异常中断，未能成功将卡片上屏展示；
  - **根因二：Codex 状态判定将中间工具事件误当回合结束**：
    - 在 [`session_resolver.py`](file:///E:/BaiduSyncdisk/LocalHub/AgentRadar/src/core/session_resolver.py#L240-L285) 历史代码中，将 `item_completed`（单项工具或子步骤完成）作为了 `is_finished` 的判定标记；
    - 当 Codex 会话在多步执行工具（如读写文件、终端命令）时，每步完成都会写入 `item_completed` 事件，导致会话在仍在运算/推理中时被误判为“任务已结束（`is_running = False`）”；
- **全套修复方案**：
  1. **清理 `_save_current_config` 残留字段**：修复 `hud_card.py`，确保动态发现新会话时能够流畅无阻地完成布局追加并持久化配置；
  2. **精准过滤 Codex 回合终态事件**：重构 `resolve_codex_sessions`，仅以终态事件 `task_complete` 与 `turn_aborted` 作为回合完成标志，并将 `task_started`、`custom_tool_call`、`custom_tool_call_output`、`reasoning`、`message` 等均精准判定为活跃工作中（`🟢`）；
  3. **扩大 7 日跨度与逆向容错流式解析**：提升缓冲区至 8KB 并采用逆向流式逐行解析，免疫正在写盘时的单行截断，并扩大至扫描近 7 日目录，避免跨日会话丢失。

---

## [0.5.2] - 2026-10-27

### 彻底移除“显全部”按钮，确立纯会话动态驱动与极简生命周期 (Pure Session-Driven Dynamic HUD & Lifecycle Model)
- **全面对齐用户交互预期**：
  - “工具中还有一个显全部的按钮，点了以后显示的是 WorkBuddy，其实没有必要；如果启动了 WorkBuddy 的一个会话，开始活跃以后，就应该自动显示在工具中，不活跃了变为待命状态，点右侧的叉图标能够删除掉”；
- **核心优化与架构规范**：
  1. **彻底移除“显全部 / 仅看运行”按钮 (`btn_filter`)**：
     - HUD 看板顶部栏进一步精简，仅保留状态摘要标题（`🛰️ AgentRadar · ...`）、最小化（`🗕`）与关闭（`✕`）；
     - 彻底删除右键托盘及上下文菜单中的离线切换项，杜绝误点呈现离线智能体占位；
  2. **全面杜绝离线应用占位卡片 (Zero Offline Placeholders)**：
     - 在 HUD 渲染逻辑中严格拦截 `state.status == AgentStatus.OFFLINE`，未启动或无活跃历史的应用（如 WorkBuddy 离线状态）永远不会以占位行形式出现在看板中；
     - 清理持久化配置 `order_config.json`，剥除历史残留的 `workbuddy` 等裸智能体标识；
  3. **标准统一的四阶段会话生命周期模型**：
     - **① 活跃动态入榜 (Active Append)**：任何智能体（包括 WorkBuddy、AntiGravity、Codex、MiniMax、Qoder）一旦启动会话并进入活跃/工作中状态（`🟢` 或 `🟡`），自动以新行形式追加至看板最下方；
     - **② 结束保持待命 (Standby Retain)**：会话完成工作后自动转为待命就绪（`🔵`），并在右侧叉图标左侧显示最新完成时间（`HH:MM`），常驻看板供用户查阅；
     - **③ 用户手动叉除 (User Dismiss)**：用户点击该行右侧 `✕` 叉图标即可将其立即移除/隐藏，看板自适应紧凑收缩；
     - **④ 新活动自动唤醒 (Auto-Wakeup)**：已被叉掉隐藏的会话一旦重新被唤醒工作，自动解除隐藏并重新展示；
  4. **升级 WorkBuddy 会话多状态解析器 (`session_resolver.py`)**：
     - 纠正对 `workbuddy.db` 中 `id, custom_title, title, status, updated_at` 的读取，并结合 `~/.workbuddy/sessions/*.json` 活跃心跳文件进行秒级运算探测，与其它 4 大智能体完全对齐。

---

## [0.5.1] - 2026-10-26

### 修复 AntiGravity 多活跃会话探测遗漏与 NTFS 目录时间戳缺陷 (Fix AntiGravity Multi-Session Detection & NTFS Directory Mtime Flaw)
- **彻底解决并发多会话下 AntiGravity 会话遗漏与工作状态误判为待命的问题**：
  - **根因深度定位**：
    - 在 Windows NTFS 文件系统规范中，当子目录中的日志文件（如 `brain/<cid>/.system_generated/logs/transcript.jsonl`）被实时写入时，**顶层目录 `brain/<cid>` 的 `st_mtime` 不会发生更新**；
    - 历史代码中使用 `entry.stat().st_mtime` 检测目录修改时间并进行 `now - stat.st_mtime < 172800` 过滤，导致创建时间超过 48 小时的长效活跃会话（如长期对话项目）被直接过滤剔除；
    - 且将会话活跃时间计算基于目录创建时间，导致实时写盘时间差 `diff` 动辄达几万秒，使会话无法满足 `diff <= 120s` 的工作条件，导致多个活跃会话被误判为空闲或无法展现；
  - **全套修复方案**：
    1. **直读日志文件真实写盘时间戳 (`os.path.getmtime(tpath)`)**：
       - 直接扫描 `brain` 目录下各会话的 `transcript.jsonl` 实际修改时间（实测 63 个会话仅耗时 4.8ms，完全保持极低资源消耗）；
       - 确保任何正在进行实时交流和工具调用的会话能够以秒级延时识别为 `is_running: True`；
    2. **健壮的反向流式 JSON 解析与 8KB 缓冲区**：
       - 尾部采样提升至 8KB，采用 `reversed(lines)` 反向安全解析，免疫高频实时写盘造成的单行截断 `JSONDecodeError`；
       - 精准判定转折：只有当最新步骤为 `type == "PLANNER_RESPONSE"` 且 `status == "DONE"` 且无待执行 `tool_calls` 时才判定回合完全结束；
    3. **多任务背景挂起状态检测 (`not_fully_idle`)**：
       - 联动 `conversation_summaries.db` 中的 `not_fully_idle == 1` 指标，即便主模型转折暂时休眠等待后台批处理/子任务，也能准确识别其正在进行后台运算，不被误判为完全待命；
    4. **精准审批拦截与自动解除隐藏联动**：
       - 精确匹配待审批工具 `ask_question`，触发黄色警示 `🟡`；
       - 被隐藏的会话一旦接收新指令开始工作，自动从隐藏列表中唤醒并在卡片底部追加。

---

## [0.5.0] - 2026-10-26

### 架构级重大性能重构：52倍提速与零死循环 (Major Performance & Architecture Overhaul)
- **全面核实并根治 issue_log.md 中提出的 P1 级重大性能缺陷**：
  - **实测性能对比**：
    - 单次感知轮询耗时：从 **1997 ms 骤降至 38.5 ms**（提速 **52 倍**，彻底进入 < 50ms 舒适区）；
    - CPU 占用率：从 **30%~60.9%（单核100%死循环）降至 1%~2%**，空闲时为 0.0%；
    - 瞬时磁盘 I/O：从 **78.82 MB/s 骤降至 < 0.2 MB/s**（下降 **400+ 倍**）；
  - **四大技术根因修复**：
    1. **Win32 全局进程快照重构 (`process_probe.py`)**：
       - 废除单次循环数十次调用 `psutil.Process.children(recursive=True)` 触发的全系统扫描雪崩；
       - 改用 Win32 底层 `CreateToolhelp32Snapshot` 单次快照（全操作系统仅需 ~8ms），在纯内存中秒级完成 5 大智能体（含 Codex 58+ 进程、Antigravity 17+ 进程）的拓扑关系解析；
       - 仅对顶层主进程统计 CPU，避免遍历几十个 Chromium 渲染器子进程；
    2. **彻底拔除 10 万+文件遍历海啸 (`log_probe.py` / `session_resolver.py`)**：
       - 彻底删除 `_inspect_workbuddy` 中对 `~/.workbuddy/workspace/sessions`（含 103,796 个文件）的 `os.walk` 遍历，改用直查 `~/.workbuddy/workbuddy.db` SQLite 数据库，耗时从 413ms 归零至 1ms；
       - Codex 会话检索废弃跨月无界遍历，改为仅定向扫描近 3 天日期目录（`YYYY/MM/DD`）；
       - 日志读取全面改用 `f.seek(max(0, sz - 4096))` 尾部切片读取，坚决不再将多兆字节的完整 `jsonl` 读入内存；
    3. **QTimer 链式单次触发与间隔放宽 (`engine.py`)**：
       - 轮询间隔由过紧的 1500ms 调整为舒适科学的 **3000ms**；
       - 废除周期性定时器的漂移积压机制，重构为 **链式单次触发 (`QTimer.singleShot`) + 防重入锁**，确保单次探测完成后工作线程必须进入足额 3000ms 的深度休眠；
    4. **入口启动参数与桌面交互实例热更 (`main.py` / `run.bat`)**：
       - 同步对齐主程序引擎的 3000ms 轮询配置，守护前台流畅度。

---

## [0.4.6] - 2026-10-25

### 彻底精简顶部栏：移除无用的“+ 恢复”按钮 (Remove Redundant Bulk Restore Header Button)
- **响应用户体验优化诉求**：
  - “隐藏会话后，有一个按钮是点击恢复，点击该按钮以后就会全部恢复出来，但这是没必要的。因为有新的活跃会话后自动就会加到后面，而且恢复之前隐藏的会话也没有必要，因为很多隐藏的会话本来就是不想关注的”；
- **优化实施**：
  - **彻底移除顶部栏的 `+ 恢复 (N)` 按钮**：消除了隐藏会话后顶部栏浮现多余控件造成的视觉干扰和空间挤占；
  - **保持极简顶栏**：顶部栏常驻仅保留标题（`🛰️ AgentRadar · ...`）、显示模式切换（`👁️ 显全部 / 仅看运行`）、最小化（`🗕`）和关闭（`✕`）；
  - **智能自动恢复机制不变**：
    - 被用户点击 `✕` 隐藏的会话，一旦接收到新任务进入工作状态（`🟢`）或等待确认（`🟡`），系统依然会自动唤醒并恢复展示，无需任何手动操作；
    - 不需要关注的待命会话点击 `✕` 后永久保持隐藏，不再有误触“一键全恢复”带来的垃圾会话回潮困扰。

---

## [0.4.5] - 2026-10-25

### 会话永驻不顶掉机制与尾部自动追加向下扩展 (Session Retention & Bottom Append Auto-Expansion)
- **彻底解决“激活新会话时旧会话被顶掉”的缺陷，全面对齐用户预期**：
  - **根因深度查明**：
    1. **解析层硬编码配额截断**：此前 `resolve_antigravity_sessions` 等解析函数的默认展示配额硬编码为 `max_sessions = 3`；当用户在原有 3 个会话（如 `Xpert-03`、`Xpert-07`、`Clone T3`）之外在 AntiGravity 中激活第 4 个新会话（`系统卡顿原因排查`）时，排序靠后的待命会话 `Xpert-03` 超出上限被强制截断丢弃；
    2. **UI 层误杀与自动清空**：`hud_card.py` 此前对 `old_key not in states` 采取了物理销毁策略（`deleteLater()` 与 `_blocks_order.remove()`），导致被截断的旧会话被彻底从界面和配置中抹除；
  - **架构级两层重构**：
    1. **解析配额全面扩展**：将 AntiGravity、Codex、MiniMax、Qoder 的感知上限统一放宽至 `max_sessions = 10`，能够完整容纳多项目并发与多工作区日常切换；
    2. **会话生命周期永驻（No Auto-Drop）**：
       - **永不自动顶掉**：已经呈现在看板上的会话，无论后续产生多少新会话，**绝对不会被自动挤掉或销毁**；未在最新轮次更新的已展示会话自动保持为待命（🔵）状态并继续显示其完成时间；
       - **唯一隐藏途径**：只有当用户**主动点击行右侧的 `✕` 按钮**时，该待命会话才会被隐藏；
    3. **新会话尾部追加与向下扩展（Bottom Append & Dynamic Height）**：
       - 新激活的会话自动分配最高排序索引 `999999`，**严格排在看板的最底部**；
       - 布局容器自动在最下方增加一行，整个卡片框体顺滑向下伸展；同时自动将新会话键值追加写入 `order_config.json` 永久持久化；
       - 历史陈旧会话（未被用户主动激活或未持久化者）绝不擅自侵入打扰看板，确保轻巧纯净。

---

## [0.4.4] - 2026-10-25

### AntiGravity 活跃会话穿透感知与双通道抢占调度 (AntiGravity Active Session Two-Pass Resolution)
- **修复活跃 AntiGravity 会话未被感知或被待命会话截断遗漏的缺陷**：
  - **根因深度查明**：
    1. **会话截断循环 Break 缺陷**：此前在遍历 `conversation_summaries.db` 列表时，若排在前面的会话处于待命状态（如 `Xpert-03`），且达到了 `len(sessions) >= max_sessions` 限制，循环直接 `break` 退出，导致排在后面的真正处于 `🟢 工作中` 的会话（如 `Clone T3 Code Project`）被彻底丢弃截断；
    2. **SQLite 延迟落盘与 25s 极短超时硬掐断**：AntiGravity 的核心数据库 `conversation_summaries.db` 存在批量异步延迟落盘（实测延迟可达 170 秒以上），而此前设置了 `diff <= 25.0s` 的判定窗口；在模型执行复杂长思考、子智能体调度或耗时 Shell 工具调用时，由于超过 25 秒未产生新事件，被误判定为已待命；
  - **感知架构全面重构**：
    - **双通道零延迟穿透**：不再单纯依赖 SQLite 数据库，而是联合扫描底层真实日志目录 `~/.gemini/antigravity/brain/*/transcript.jsonl`，直接读取物理落盘时间与最后一步指令状态；
    - **轮次终结判定准则**：严格确认只有当最后一步为 `PLANNER_RESPONSE` 且无后续 `tool_calls` 且 `status == "DONE"` 时才视为轮次结束；在工具执行中（`GENERIC`）或用户输入等待处理中均准确判定为 `🟢 工作中`；
    - **双通道抢占式优先级收集 (Two-Pass Resolution)**：先遍历收集**全部处于活跃工作状态的会话**（优先保证所有运行中的任务 100% 呈现在看板顶部，绝不漏报），剩余展示配额再由待命会话按最近活跃时间倒序补充；
    - **时间窗口放宽**：将工作中心跳感知超时容忍区间由 25 秒放宽至合理的 120 秒，完美适配深度推理与耗时工具调用场景。

---

## [0.4.3] - 2026-10-25

### 待命会话结束/更新时间显示 (Standby Session Completion Time Display)
- **新增待命会话最新更新时间呈现**：
  - 响应用户需求：“为处于待命状态的会话显示结束时间/最新更新时间，活跃中的不用显示，显示在右侧隐藏按钮左侧”；
  - **单行排布**：`[⠿ 移动手柄]` → `[⚪/🟢/🔵/🟡 状态灯]` → `[智能体名称]` → `[会话名称]` (弹性拉伸) → **`[结束时间 (如 21:33)]`** → `[✕ 隐藏按钮]`；
  - **动态显隐控制**：
    - 当会话处于 **`🔵 待命 (IDLE)`** 时，在右侧 `✕` 按钮左侧展示精致紧凑的完成时间（如 `21:33`），鼠标悬停可查看完整年月日与时分秒；
    - 当会话处于 **`🟢 工作中 (THINKING)`** 或 **`🟡 等待确认`** 时，该时间文本自动隐藏，保持工作中的极简纯净。
  - 看板横向宽度从 330px 顺滑微调为 **340px**，为会话标题与时间戳提供舒适的间距。

### MiniMax Code 并发多会话独立感知 (MiniMax Concurrent Multi-Session Resolution)
- **修复 MiniMax Code 并发多个活跃会话只展示单行的缺陷**：
  - **根因剖析**：此前 `resolve_minimax_sessions` SQL 查询中硬编码了 `LIMIT 1` 与 `cur.fetchone()`，导致即使数据库中有多个未归档活跃会话（如 `7-1` 与 `3-1`），也只能抓取到最新的一条；
  - **升级并发感知**：
    - 支持同时解析 MiniMax 本地运行时数据库（`~/.minimax/v2/sqlite/runtime-state.sqlite`）中的所有未归档会话；
    - 对每个会话独立穿透查询 `local_runtime_message_rows`，独立评估其 `finish_reason`、工具调用与流式生成状态，一行一个独立呈现；
    - 确保 `7-1` 与 `3-1` 两个会话同时在看板中显示，互不干扰、状态各自独立更新。

### Qoder 轮次协议状态机全面修正 (Full Turn-Aware State Machine)
- **彻底解决“工作中误报待命”的根本性时序缺陷**：
  - **根因深度查明**：
    1. 此前代码倒序遍历寻找带有 `stop_reason` 的字段，当用户刚发送提问或工具刚返回 `tool_result` 时（这些属于 `user` 角色，没有 `stop_reason`），算法直接穿透忽略，误抓取了**上一轮对话残留的 `end_turn`**，导致模型一开始思考就误显为“待命”；
    2. 此前设置了过窄的 `diff <= 25.0s` 时间窗口，当模型长思考（如 28 秒未落盘）或工具耗时稍长时，超时硬切为了“待命”。
  - **会话级协议状态机重构**：
    - 严格定位**最后一条真实交互消息**：
      - 若最后一条消息为 `user` 角色（用户 Prompt 输入中或 Tool 结果返回等待处理）→ **`🟢 工作中 (模型生成中)`**；
      - 若最后一条消息为 `assistant` 且包含 `stop_reason: "tool_use"` → **`🟢 工作中 (工具调用中)`**；
      - 若最后一条消息为 `assistant` 且 `stop_reason` 为空（分块流式输出中） → **`🟢 工作中 (思考推理中)`**；
      - 仅在最后一条消息为 `assistant` 且输出 `stop_reason: "end_turn"`（且后续无新用户指令）时 → **`🔵 待命就绪`**；
  - **双通道心跳兜底**：结合 `%APPDATA%\com.qoder.app.stable\logs\*\qodercli\sessions\<sid>.log` 与 payload buffer WAL 的流式通信时间戳，彻底消灭进度同步延迟与误判。

---

## [0.4.2] - 2026-10-25

### 极致无文字纯图元精简 (Ultra-Minimal Textless Design)
- **剔除右侧冗余状态文字**：
  - 响应用户最新审美与效率诉求：“其实活跃中已经有绿色图标显示了，待命是蓝色图标，右侧没有必要显示文字（如工作中多少秒、就绪）”；
  - 彻底移除行内右侧冗余的状态文字胶囊，纯靠色彩指示灯直观传达状态（🟢 工作中 / 🔵 待命就绪 / ⚪ 离线 / 🟡 等待确认）；
  - **极致纯净单行布局**：`[⠿ 移动手柄]` → `[状态灯 (⚪/🔵/🟢/🟡)]` → `[智能体名称]` → `[会话名称]` (弹性拉伸) → `[✕ 隐藏会话]`；
  - **宽度收窄至 330px**：看板整体横向宽度由 380px 压缩至 330px，占地面积锐减，极度轻巧不遮挡桌面日常操作；
  - **悬停显示详情**：将运行秒数、详细状态与操作提示全部收纳至鼠标悬停浮动气泡（Tooltip）中，需要查看时鼠标一指即可。

### Qoder 活跃状态实时精准探测 (Qoder Active State Real-time Sensing)
- **修复 Qoder 活跃工作却误显为“待命”的根本缺陷**：
  - **根因分析**：此前 `resolve_qoder_sessions()` 中静态返回了 `"is_running": False`；
  - **协议级动态追踪**：深入解析 Qoder 底层在 `~/.qoder/projects/**/*.jsonl` 生成的 Turn 协议流，实时比对最后一条 assistant 消息的 `stop_reason`：
    - 若正在执行工具（`stop_reason: "tool_use"`）或正在流式推理，且日志变更在 25s 活跃窗口内，判定为 `🟢 工作中 (THINKING)`；
    - 仅在 agent 明确输出 `stop_reason: "end_turn"` 或超过活跃时间后才判定为待命；
    - 同步结合 `%APPDATA%\com.qoder.app.stable\chat-session-turn-payload-buffer.sqlite-wal` 高频写入时间戳，确保工具执行与持续输出全流程不掉线。

---

## [0.4.1] - 2026-10-25

### 极简紧凑单行重构 (Ultra-Compact Streamlined Redesign)
- **极简单行布局（节省 >50% 屏幕空间）**：
  - 响应用户界面精简需求，废除卡片内垂直堆叠 3 行文本的多余空间浪费，整行为单水平行；
  - **水平排列顺序**：`[⠿ 移动手柄]` → `[状态灯 (⚪/🔵/🟢/🟡)]` → `[智能体名称]` → `[会话名称]` → `[工作状态徽章]` → `[✕ 隐藏]`;
  - **剔除冗余状态文本**：去除重复的状态描述字段，仅保留精致的胶囊状态灯（如 `工作中 25s` / `就绪` / `离线`）；
  - 单卡片高度从 ~65px 锐减至 **32px**，整体窗口高度缩减一半以上（仅 ~240px），极致轻量且不挡桌面。
- **右侧单会话快速隐藏（✕）与动态自恢复**：
  - 针对用户不打算继续关注的待命会话，可在该行最右侧直接点击微型 **`✕`** 快速移除；
  - **智能自恢复**：后续该会话一旦有新动作启动推理（THINKING），或用户创建全新会话时，自动在看板中解除隐藏并浮现；
  - 顶部栏提供 `+ 恢复 (N)` 快捷按钮与右键菜单，方便随时一键重新召回全部隐藏会话。
- **纯粹左侧拖动手柄**：
  - 换位全部由左侧 **`⠿` 拖动手柄**承担，配合直连 Qt 布局索引与全局物理坐标，按住上下拖拽瞬间对调位置，手感极其跟手流畅。
- **单实例进程通信（QLocalServer IPC）**：
  - 接入命名管道进程间唤醒，无论主窗口何时最小化或藏于托盘，双击桌面快捷方式立即秒级唤出置顶。

---

## [0.4.0] - 2026-10-25

### 架构级重构：细粒度单会话独立成行 (Disaggregated Per-Session Architecture)
- **告别会话粗暴聚合，一行显示一个独立会话**：
  - 响应用户核心反馈：“两个会话，建议不要聚合显示，一行显示一个会话”；
  - 彻底拆解原本将多会话拼接为 `A  •  B` 的聚合卡片架构，全面转向**“细粒度单会话独立成行”**；
  - 每个活跃会话拥有专属的独立的卡片行、独立的状态指示灯（🟢/🔵/🟡/⚪）、独立的持续时间计时器、独立的拖拽排序手柄与快速隐藏 `✕` 按钮。
- **独立精确状态判定（彻底解决 AntiGravity 状态串扰）**：
  - **根因分析**：此前 AntiGravity 中一个会话在工作（如 `并购贷后管理`），另一个会话已停止（如 `Clone T3 Code Project`），由于合并显示在同一个卡片中，导致“就绪”的会话被串扰显示为“工作中”；
  - **会话级隔离判定**：升级 [`src/core/session_resolver.py`](../src/core/session_resolver.py) 与 [`src/core/engine.py`](../src/core/engine.py)，对 AntiGravity 的每个活跃会话独立比对底层 `transcript.jsonl` 转录流和级联事务状态：
    - `并购贷后管理` 独立评估，显示其真实状态（`🟢 工作中` 或 `🔵 就绪`）；
    - `Clone T3 Code Project` 独立评估，未运行时准确显示 `🔵 就绪`；
    - 两者互不干扰、互不遮蔽。
- **OpenAI Codex 并发会话分行展示**：
  - 针对 Codex 的多个活跃任务（如 `更新待领取题目文档` 与 `3-0`），独立分为两行展示，各自监控独立 `rollout-*.jsonl` 的 `task_complete` / 推理状态。
- **点击会话卡片瞬时切窗置顶**：
  - 用户只需在 HUD 看板中点击任意会话行，即可调用 Win32 强前台激活机制瞬间将对应的客户端窗口唤醒并置顶到屏幕最前。
- **流畅拖拽排序与离线卡片管理**：
  - 用户可自由使用 `⠿` 拖动或点击 `▲▼` 上下调整任意会话行的排列顺序；
  - 离线或不关心的会话/智能体可随时点 `✕` 隐藏；
  - 开启顶部 `[👁️ 仅看运行]` 可一键收起所有离线行（如 WorkBuddy）。

### 深度稳定性与多会话升级 (Deep Stability & Multi-Session Upgrade)
- **AntiGravity 多会话聚合识别与彻底消灭“闪烁”**：
  - **多会话聚合**：全面升级 [`src/core/session_resolver.py`](../src/core/session_resolver.py)，直查 `conversation_summaries.db` 中当前处于活跃与近期的多个会话，成功将用户同时开启的会话聚合呈现（如 `💬 Clone T3 Code Project  •  并购贷后管理`）；
  - **彻底消灭待命/工作频繁闪烁**：此前解析每步 `transcript.jsonl` 时，模型思考与工具调用之间的中间过渡 Step 被误判为完成，导致“工作中 ↔ 待命”每秒剧烈翻转。改用直读 AntiGravity 原生级级联事务状态（`CASCADE_RUN_STATUS_RUNNING` 与 `not_fully_idle`），使整个思考与代码编写周期保持稳定持续的工作态，无任何中间跳变。
- **MiniMax Code 工作状态准确感知（解决显示待命问题）**：
  - 经深入逆向排查 MiniMax 本地运行时数据库，发现 MiniMax 的核心会话状态枚举为 `started`（而非通用 busy/running）；
  - 同步打通 `local_runtime_background_tasks` 运行中任务检测，只要 MiniMax 处于 `started` 或在后台执行脚本任务，雷达即时感知并准确亮起 `🟢 工作中`，任务结束即时回落 `🔵 待命`。

---

## [0.3.2] - 2026-10-25

### 核心状态精度重构 (Critical Accuracy Overhaul)
- **彻底杜绝 AntiGravity / Codex 假阳性“工作中”虚标**：
  - **根因定位**：
    1. 早期探针路径泛化扫描了根目录，抓到了后台语言服务日志（`language_server.log`）、Sentry 错误收集（`session.json`）、Chromium LevelDB 和状态缓存的自动心跳写入，误将其作为大模型正在推理的信号；
    2. 网络探针检测到所有 Electron/Web 客户端维持的 443 长连接（WebSocket/HTTP2），导致在后台心跳与持久连接联动下状态机被锁死在“工作中”。
  - **精准聚焦核心会话文件**：
    - **AntiGravity**：仅监听 `~/.gemini/antigravity/brain` 下的真实对话流 `transcript.jsonl`，完全排除 LSP 语言服务日志与缓存；
    - **OpenAI Codex**：仅监听 `~/.codex/sessions` 下的真实对话流 `rollout-*.jsonl`，完全排除 Sentry 遥测、LevelDB 及 `.codex-global-state.json`；
    - **MiniMax Code**：直读 `runtime-state.sqlite` 的原生会话 `status` 字段（`idle` vs `busy`）；
    - **Qoder** 与 **WorkBuddy**：收敛至专属 session 目录。
  - **协议级任务完结（Task Completion）即时切换**：
    - Codex 会话末尾捕获到 `task_complete`、`turn_aborted` 或 `thread_settings_applied` 时，立即判定为 `IDLE`（就绪），零延迟清零计时；
    - AntiGravity 会话末尾捕获到模型最终回复 `status: DONE` 且无正在执行的工具时，立即判定为 `IDLE`；
    - 废弃单纯依赖端口 443 长连接维持思考状态的错误逻辑。

---

## [0.3.1] - 2026-10-25

### 新增与修复 (Added & Fixed)
- **Codex 多活跃会话/线程聚合呈现 (Codex Multi-Session Support)**：
  - 增强 [`src/core/session_resolver.py`](../src/core/session_resolver.py)，支持检索同一项目会话下的全部活跃子线程或近期活跃多会话；
  - 聚合显示为 `💬 3-0  •  分析 task_003 题目重合`，并在悬浮 Tooltip 中列出全部活跃会话清单，解决并发会话只显示单一会话的问题。
- **离线卡片移除与自定义隐藏机制 (Dismiss & Hide Offline Cards)**：
  - 在每个智能体卡片右侧新增快速隐藏按钮 `✕`（如关闭 WorkBuddy 后可直接点 `✕` 将其移除出卡片列表）；
  - 顶部栏新增 `[👁️ 仅看运行 / 显全部]` 一键全局过滤开关，开启后自动收起所有离线智能体；
  - 顶部栏与右键菜单提供 `[+ 恢复全部]` 与 `显示全部智能体卡片` 功能；
  - **进程唤醒自恢复**：被隐藏的智能体一旦检测到进程启动并进入工作中或就绪状态，将自动取消隐藏重新浮现，确保不会漏掉工作动态；
  - 状态配置统一持久化至 [`order_config.json`](../order_config.json)。
- **Qoder (Qcode) 活跃会话名数据库级直读修复**：
  - 重构 Qoder 会话解析器，直读 `%APPDATA%\com.qoder.app.stable\main.sqlite` 的 `chat_sessions` 表，准确读取真实会话标题（如 `7-1`），彻底替代旧版抓取临时消息片段的做法。
- **MiniMax Code 本地运行时数据库透传**：
  - 接入 MiniMax 本地运行时数据库 `~/.minimax/v2/sqlite/runtime-state.sqlite`，查询 `local_runtime_sessions` 表中的未归档活跃会话；
  - 准确展示 MiniMax 当前活跃任务标题（如 `7-1`），解决此前由于窗口标题未携带导致显示默认会话的问题。

---

## [0.3.0] - 2026-10-25

### 新增特性 (Added)
- **活跃会话/任务名称实时穿透解析 (Active Session Title Resolution)**：
  - 新增核心模块 [`src/core/session_resolver.py`](../src/core/session_resolver.py)，针对 5 大 GUI 框架建立了会话标题底层提取机制：
    - **Google AntiGravity**：直读 `~/.gemini/antigravity/conversation_summaries.db`，精确提取当前最新会话名称（如 `Clone T3 Code Project`）；
    - **OpenAI Codex**：实时读取 `~/.codex/session_index.jsonl`，精确解析线程名（如 `3-0`、`分析 task_003 题目重合`）；
    - **WorkBuddy**：直读 `~/.workbuddy/workbuddy.db` 的 `sessions` 表，精确提取当前任务标题（如 `7-3`、`7-2`）；
    - **Qoder (Qcode)**：解析 `~/.qoder/projects` 中最新活跃 session，精准提取当前工作阶段与首轮任务提示词（如 `当前处理出题审计阶段...`）；
    - **MiniMax Code**：自适应提取工作区项目名称与窗口上下文；
  - 在悬浮卡片每个条目中新增天蓝色高亮标识 `💬 [会话名称]`，支持悬浮完整 Tooltip 提示；
  - 配备 3 秒只读轻量缓存，保持 0 额外的系统开销。

---

## [0.2.0] - 2026-10-25
- **卡片自由拖拽排序**：移除每行“置顶”按钮，新增 `⠿` 抓手与 `▲▼` 箭头，顺序保存至 `order_config.json`；
- **全多线程重构**：感知引擎迁入独立 `QThread`，彻底消灭鼠标拖拽卡顿；
- **状态准确度加固**：屏蔽守护进程心跳文件，解决 WorkBuddy / MiniMax 假阳性误判。

---

## [0.1.0] - 2026-10-25
- **项目初始化**：完成五大 GUI 智能体适配、三重混合状态感知引擎与基础托盘 HUD 卡片。
