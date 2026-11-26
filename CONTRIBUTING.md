# 开发指南

## 建立环境

使用 Windows、PowerShell 7、Python 3.12 和 Node.js 24。命令均在仓库根目录执行。

```powershell
.\scripts\setup.ps1
npm ci
.\scripts\test.ps1
```

`setup.ps1` 创建 `.venv`，从 `requirements.lock` 安装依赖，再以 editable 方式安装本项目。
`npm ci` 使用 `package-lock.json`；前端与行为包运行时不携带 `node_modules`。

如果设备策略不允许执行 PowerShell 脚本，可在允许的终端执行等价 Python 命令：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

## 代码约定

- 类、函数和方法写明职责，关键业务规则说明原因。
- 一个方法负责一件事，避免长方法和深层分支；使用清晰业务名称。
- LessonEngine 是课程状态权威；适配器负责证据与效果，不复制判分规则。
- AI 不得直接写成绩、改任务或执行任意 Minecraft 命令。
- 游戏、语音和控制来源分离；新请求使用新 ID，重试必须保留原 ID、序号和正文。
- 不记录原始录音、真实身份、完整自由对话或秘密。
- 未经实机验证的 Minecraft API、素材标识、效果及耗时必须标为待验证。

项目内的 [AGENTS.md](AGENTS.md) 同样适用于后续代码修改。

## 修改后检查

```powershell
.\.venv\Scripts\python.exe -m ruff format backend scripts
.\.venv\Scripts\python.exe -m ruff check backend scripts
.\.venv\Scripts\python.exe -X utf8 scripts/check_readability.py
npm run format
npm run check
.\scripts\test.ps1
```

`test.ps1` 依次运行 pytest、Ruff、Python 职责注释检查、Node 测试、ESLint、两套 Minecraft API 类型检查和 Prettier。
前后端的单元测试不需要启动游戏；测试使用临时 SQLite 数据库。

关键回归包括事件幂等、错玩家/任务、提示归因、暂停恢复、可选口语、音频结束、BDS 绑定、可见性失效和奖励重投。
新增测试应验证可观察行为和故障边界，不照抄实现。

## 更新接口与行为包

接口模型或路由改变后重新生成契约：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/export_contract.py
```

测试会比较 `contracts/openapi.yaml` 与实际 FastAPI 导出结果，防止漂移。

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/build_bedrock.py
```

生成文件在 `dist/`。构建器按入口追踪本地模块依赖，包内不含服务器秘密。
修改 Minecraft 依赖需要同时更新候选档案、开发类型依赖、锁文件和联调说明。
不能只因 `tsc` 通过就把实机项目打勾。

## 验证记录与提交

使用 `codex/` 或仓库约定的功能分支，提交聚焦的变更。说明问题、结果、验证方式和实际限制。
实机验收记录客户端/BDS/模块版本、操作步骤、预期与实际结果、脱敏日志片段和样本数量。

```powershell
git status --short
git diff --check
git diff --cached --stat
```

不要提交 `data`、`.venv`、`node_modules`、`runtime`、`dist`、数据库、令牌或实际 BDS 配置。
依赖升级需更新锁文件并重跑相关检查；修改教学规则需同步规格解释和验收测试。
