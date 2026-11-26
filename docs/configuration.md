# 配置与 HTTP 接口

## 环境变量

程序读取进程环境变量，**不会自动加载 `.env` 文件**。启动脚本仅监听 `127.0.0.1`，关闭代理头解析。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `MOCK_MODE` | `true` | 离线默认模式；BDS 候选通过专用接口和绑定单独启用；当前不支持 false |
| `DATABASE_PATH` | `data/progress.sqlite3` | 普通启动的数据库位置 |
| `API_TOKEN` | 空 | 非空时业务 API 要求 `X-API-Token`；本机页面与素材仍可加载 |
| `BDS_TOKEN` | 空 | BDS 专用接口要求 `X-BDS-Token`；为空时通道关闭 |
| `BDS_ALLOWED_HOSTS` | `127.0.0.1,::1` | BDS 实际 TCP 来源白名单，不信任转发头 |

`start_m2.ps1` 和 `start_m3.ps1` 使用 `data/m2-progress.sqlite3`，创建或复用 `data/bds-token.txt`。
脚本把 BDS_TOKEN 放入启动进程；停止后恢复原终端环境变量。
配置 BDS 时，安装器将秘密写入指定脚本 UUID 的 `secrets.json`，不写入行为包或浏览器。

若配置 API_TOKEN，运行 API 和安装器的终端需使用一致值，伴随页填同一操作员口令。
不要将真实口令写入命令示例、Git 提交或问题反馈。

## 启动和文档入口

```powershell
.\scripts\start_backend.ps1 -Port 8000
```

- 页面：`http://127.0.0.1:8000/`
- M3 伴随页：`http://127.0.0.1:8000/bedrock`
- 交互式接口文档：`http://127.0.0.1:8000/docs`
- 固定版本契约：[openapi.yaml](../contracts/openapi.yaml)

`/health` 报告服务和默认离线适配状态，不能判定某个 BDS 世界已连接。
有操作员认证时可通过携带请求头的 HTTP 客户端查看契约和业务 API。

## 通道表

| 通道 | 主要接口 | 权限与用途 |
| --- | --- | --- |
| 课次控制 | `/v1/sessions`、`/v1/sessions/{session_id}/start`、`/v1/sessions/{session_id}/control` | 操作员，创建及明确用户控制 |
| 离线游戏 | `/v1/game/events`、`/v1/game/actions` | 操作员，仅未绑定 BDS 的课次 |
| 语音 | `/v1/voice/events`、`/v1/voice/actions` | 操作员，播放/停声和媒体回执 |
| 世界绑定 | `/v1/bds/bindings`、`/v1/bds/status/{bridge_id}` | 操作员，绑定和诊断读取 |
| BDS 诊断 | `/v1/bds/probe`、`/v1/bds/context/{bridge_id}`、`/v1/bds/events` | BDS 专用令牌和来源限制 |
| M3 游戏 | `/v1/bds/lesson/*` | BDS 专用，动作、视觉、控制、ACK、耗时样本 |
| M3 音频 | `/v1/bedrock/companion/{bridge_id}`、`/v1/bedrock/audio` | 操作员，视觉租约查询与真实播放回执 |
| M3 指标 | `/v1/bedrock/metrics/{bridge_id}` | 操作员，P95 和样本数 |
| 观察报告 | `/v1/progress/{session_id}` | 操作员，本课次学习观察 |

## 创建并开始一个离线课次

以下示例用于 API 开发，不绑定真实 BDS：

```powershell
$baseUrl = 'http://127.0.0.1:8000'
$headers = @{}
if ($env:API_TOKEN) { $headers['X-API-Token'] = $env:API_TOKEN }
$create = @{ event_id = [guid]::NewGuid().ToString(); player_id = 'local_player_01' }
$session = Invoke-RestMethod -Method Post -Uri "$baseUrl/v1/sessions" -Headers $headers `
    -ContentType 'application/json' -Body ($create | ConvertTo-Json)

$start = @{
    event_id = [guid]::NewGuid().ToString()
    session_id = $session.session_id
    player_id = $session.player_id
    task_id = $session.current_task.task_id
    kind = 'START'
    sequence = 1
}
Invoke-RestMethod -Method Post -Uri "$baseUrl/v1/sessions/$($session.session_id)/start" `
    -Headers $headers -ContentType 'application/json' -Body ($start | ConvertTo-Json)
Invoke-RestMethod -Uri "$baseUrl/v1/progress/$($session.session_id)" -Headers $headers
```

重试必须复用原 body。新事件使用新 ID，并按当前课次该来源的序号递增。
重复事件返回处理当时的收据；读取最新课次请单独 GET，不用历史收据覆盖新状态。
动作 ACK 只表示传输/执行确认，不等同于教学成功。

## 本地数据

运行记录保存在 `data/`，不随仓库上传。普通课堂与 BDS 候选使用不同数据库文件。
备份时先停止服务，再保留数据库及绑定配置；运行中的 SQLite 可能同时有 WAL/SHM 文件。
不要通过删除单个去重表来“修复”序号，否则会破坏恢复语义。
家长数据删除界面仍在 M5 计划中，当前没有完整的记录管理产品能力。
