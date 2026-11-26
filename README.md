# Minecraft for English Learning

以 Minecraft 农场探索为场景的英语启蒙原型。首课围绕 **cow / pig**，通过听指令、寻找动物、提示和换场景复习建立语言与行动的联系；说话是可选项，沉默不会阻止继续游戏。

**当前版本：0.4.0，M3 开发候选版。** 离线课程与浏览器农场可运行；Bedrock/BDS 行为包已实现并通过离线检查，**尚未完成 Minecraft 实机兼容性与完整游戏流程验收**。

## 先选运行方式

| 方式 | 可以做什么 | 需要什么 | 验证状态 |
| --- | --- | --- | --- |
| M1 离线课堂 | 本地英语音频、点击动物、提示、暂停恢复、完整首课及观察报告 | Windows、Python 3.12、浏览器 | 已通过浏览器流程检查 |
| M2 事件诊断 | 牛/猪原生事件、BDS 到 API 的 HTTP 通路 | 国际版 Bedrock + BDS | 代码与离线测试完成，实机待验 |
| M3 游戏闭环 | 农场与 Lily、游戏选择、提示、奖励、语音伴随、耗时采样 | 通过 M2 门槛的 BDS + 匹配客户端 | 候选包，实机待验 |

第一次接触项目，建议先运行 M1。M1 不需要 Minecraft、麦克风、云端 AI 服务或服务商密钥。

## 快速开始：离线课堂

安装 Git、Python **3.12**（含 Windows Python Launcher），使用 PowerShell 7。Node.js **24** 只用于开发检查，运行课堂页面不需要 Node。

```powershell
git clone https://github.com/shenxin2014/Minecraft_For_English_Learning.git
Set-Location Minecraft_For_English_Learning

# 创建项目内虚拟环境，安装锁定的 Python 依赖。
.\scripts\setup.ps1

# 启动本地课堂，保持终端打开。
.\scripts\start_m1.ps1
```

打开 [Lily 的小农场](http://127.0.0.1:8000/)，点击开始。
按页面完成听、看和选择，可使用“再听一次”“帮帮我”“暂停”和“跳过”，最后查看本次观察报告。
终端按 `Ctrl+C` 停止服务，重新启动后可恢复持久化课次。

首次安装需要网络。仓库包含 12 段本地合成英语 WAV，安装依赖后运行课堂无需互联网。
若 8000 端口被占用，可用 `.\scripts\start_m1.ps1 -Port 8001`，并访问对应端口。

## 进入 Minecraft：M3 候选版

目标平台是 **国际版 Minecraft for Windows（Bedrock）+ Bedrock Dedicated Server**。
本项目没有使用 Minecraft Education 的桥接协议，也不支持把 BDS 网络行为包直接当作单人客户端联网插件。

```powershell
# 生成 M2 诊断包、M2 网络候选包和 M3 候选包。
.\.venv\Scripts\python.exe -X utf8 scripts/build_bedrock.py

# 启动 BDS 配套 API 与语音伴随页面。
.\scripts\start_m3.ps1
```

M3 产物：`dist/english-farm-m3-bds-1.26.66-candidate.mcpack`。
伴随页：[Minecraft 语音伴随](http://127.0.0.1:8000/bedrock)。它播放真实音频，等待 BDS 上报场景状态，不会自己模拟动物选择。

**此处还不能直接开始游戏课程。** 先按 [M2 环境与 HTTP 验证](docs/milestone-2.md)确认版本和通信，再按 [M3 安装与联调](docs/milestone-3.md)安装到专用测试世界、建图、探针和绑定玩家。
候选依赖锁定在 `bedrock-pack/profiles.json`；实际安装版本若不匹配，需重新核对并实测，不能仅修改版本号就视为兼容。

## 当前能力与边界

- LessonEngine 负责课程状态与判定；客户端和 AI 不能直接写成绩或执行任意游戏命令。
- 事件按来源排序，重复请求沿用原 ID；课程状态、收据和动作队列由 SQLite 事务保存。
- 区分独立正确、提示后正确和未确认正确；剧情完成不等于词汇掌握。
- H1–H4 逐级提示，口语环节可跳过，播放失败不计有效输入。
- M3 通过固定世界状态实现开门和装饰奖励，避免重发时追加奖励物品。
- 尚未实现真实语音识别、Electron 语音客户端、跨日期复习和完整数据删除界面，分别安排在 M4/M5。
- 尚无真实 BDS P95 测量结论；测试通过不代表游戏内性能已经达标。

## 开发与检查

```powershell
# 安装 Node.js 24 后，在仓库根目录运行。
npm ci
.\scripts\test.ps1

# 只检查 Python 后端时，不需要 Node。
.\scripts\test.ps1 -BackendOnly

# 完整 Mock 课程演示；默认使用临时数据库。
.\scripts\run_mock_demo.ps1
.\scripts\run_mock_demo.ps1 -AudioFails
```

0.4.0 的本地验证基线：**81 项 Python 测试、38 项 JavaScript 测试通过**，Ruff、职责注释、ESLint、Prettier 和 Minecraft API 类型检查通过。
测试依赖仍有一条 Starlette/HTTPX 弃用警告，未影响当前结果。完整操作见 [开发指南](CONTRIBUTING.md)。

## 文档导航

| 文档 | 内容 |
| --- | --- |
| [文档索引](docs/README.md) | 阅读顺序与文档适用范围 |
| [架构与数据流](docs/architecture.md) | 状态权威、通道、持久化与音画协作 |
| [配置与接口](docs/configuration.md) | 环境变量、认证、HTTP 示例与本地数据 |
| [常见问题](docs/troubleshooting.md) | 环境安装、音频、BDS 候选版本与恢复排查 |
| [开发指南](CONTRIBUTING.md) | 环境、代码约定、测试、契约与行为包构建 |
| [版本记录](CHANGELOG.md) | M0–M3 的交付内容与限制 |
| [顺序任务表](docs/tasks.md) | 已实现、待实机验证及后续工作 |
| [M1 验证记录](docs/milestone-1.md) | 离线课堂操作与浏览器检查 |
| [M2 联调说明](docs/milestone-2.md) | 事件诊断与 HTTP 兼容性门槛 |
| [M3 联调说明](docs/milestone-3.md) | 安装、游戏操作、恢复和 P95 验收 |
| [原始规格 V1.1](docs/Minecraft_AI_英语启蒙教学与开发规格_V1.1.md) | 产品与教学需求基线 |

## 仓库内容

```text
backend/app/        确定性课程引擎、FastAPI、SQLite、BDS 接口
backend/tests/      课程验收、边界、协议和打包测试
frontend/           M1 离线课堂、M3 语音伴随页、本地素材
bedrock-pack/       行为包源码、版本候选、游戏端测试
lessons/           完整首课配置
contracts/         从运行时导出的 OpenAPI 契约
scripts/           安装、启动、测试、打包和 BDS 配置工具
docs/              设计、操作、验证记录和路线图
```

虚拟环境、`node_modules`、数据库、令牌、真实 BDS 配置和 `dist` 生成物不提交到 Git。
克隆后需运行安装脚本；行为包可通过构建命令重新生成。
项目默认只监听本机回环地址。当前不使用麦克风，不保存儿童原始音频、真实身份或完整自由对话。
素材来源见 [第三方与素材说明](THIRD_PARTY_NOTICES.md)。
