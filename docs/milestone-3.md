# M3 游戏任务闭环候选版

版本 0.4.0，2026-11-26。代码、协议回归及浏览器伴随页检查已完成。
**尚未在目标 Minecraft for Windows + BDS 中加载验证，M3 实机 DoD 未通过。**
M2 的实际版本、模块加载和 HTTP 回传门槛仍需先在真实环境通过。
没有将教育版桥接、单元测试或浏览器模拟心跳当作国际版实机证据。

## 本次交付

| 功能 | 实现 |
| --- | --- |
| 最小农场 | 独立的 17×33 方块平台、围栏、入口、草地、木地板复习区 |
| Lily | 带名字的村民角色，交互可开始、结束观察/探索、恢复和跳过自愿口语 |
| 选择动物 | 监听原生交互意图，取消喂食/交易副作用，牛/猪选择进入课程引擎 |
| 提示 | H1 重听、H2 动物声音、H3 短期粒子高亮、H4 粒子路线 |
| 奖励 | 固定门洞设为空气、固定位置种一朵花，不追加背包物品 |
| 重试 | 发件箱保留原事件；动作执行记录保存随机布局及效果完成状态 |
| 语音 | 本地浏览器伴随页使用 M1 的 WAV 文件，真实 ended 才提交完成 |
| 音画约束 | 短期可见性租约；断线、遮挡、任务变化使旧播放代次失效 |
| 反馈耗时 | 原始选择事件到 PLAY_FEEDBACK 执行的同机计时、去重样本与 P95 |

动作执行只支持固定类型和目标；没有拼接或执行来自 API 的 Minecraft 命令。
类和方法有职责注释，JavaScript 复杂度上限 8、函数长度上限 60 行，Python 复杂度上限 8。

## 文件与启动

行为包：`dist/english-farm-m3-bds-1.26.66-candidate.mcpack`。
清单版本 0.4.0，独立 UUID，不覆盖 M2 包。
模块候选沿用 server 2.11.0、server-net/admin 1.0.0-beta.1.26.66-stable；
类型检查通过不表示运行时加载通过。实际 BDS 若拒绝依赖版本，需按日志校准候选档案。

```powershell
# 在克隆后的仓库根目录执行。
.\.venv\Scripts\python.exe -X utf8 scripts/build_bedrock.py
.\scripts\start_m3.ps1
```

语音伴随页：`http://127.0.0.1:8000/bedrock`。
M1 离线课堂仍保留在 `/`，两个页面的重试存储相互隔离。
M3 启动复用 BDS 私密令牌与 `data/m2-progress.sqlite3`；课次和世界使用新的绑定。
默认 `MOCK_MODE=true` 表示仍保留离线默认模式，BDS 候选接口由令牌及绑定单独启用。
`/health` 不用来判断游戏是否在线；使用对应桥接的探针与伴随页状态。

## 安装到 BDS

1. 先完成 M2 的版本与 HTTP 门槛检查。
2. 在与候选匹配的国际版客户端准备一个**专用平坦、创造模式测试世界**，开启 Beta APIs 和测试指令权限。
3. 部署到 BDS 的 `worlds`，确保 `server.properties` 的 `level-name` 指向该世界。
4. 正常停止 BDS，并保持本地 API 已启动。
5. 在第二个终端运行，替换示例目录和世界名：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/configure_bds.py `
  --bds-dir 'D:\MinecraftBDS' --world-name 'Farm M3' `
  --bds-version '1.26.66' --bridge-id 'farm_m3_01' `
  --profile 'm3-bds-1.26.66-candidate'
```

安装目录为 `behavior_packs/english_farm_m3`，权限和秘密放在当前脚本 UUID 的配置目录。
世界包列表备份为 `world_behavior_packs.before-m3.json`。
安装器拒绝覆盖已有安装，也拒绝在同一世界同时启用本项目的不同版本。
不要直接把网络包当作普通客户端单人世界的联网插件；网络执行仍在 BDS。

## 游戏内操作

启动 BDS，确认无脚本模块错误后，用国际版客户端加入。
在空旷平坦区域依次执行：

```text
/scriptevent farm:build
/scriptevent farm:probe
/scriptevent farm:bind
```

等探针成功提示后再绑定。建图前会检查完整保留区为空气，不会覆盖已有建筑。
平台在玩家附近偏移并抬高，建好后传送到入口；建议保持创造模式。
建图仅允许一次。若建图中途失败，保留原区域作诊断并用新的测试世界重试，不自动抹除地形。

在伴随页输入 `farm_m3_01`，如配置了 API_TOKEN 则输入操作员口令，点击“连接并启用声音”。
浏览器不需要 BDS_TOKEN，也不会保存口令。保持页面打开并返回 Minecraft。

- 与 Lily 交互开始课程；观察或探索结束后再次交互继续。
- 听到找动物指令后，对对应动物使用交互键。行为包取消原始喂食/交易，仅提交选择意图。
- 进入新视觉任务时传送到观察点；动物左右位置在执行前随机并持久化。
- 想重听、求助、暂停或跳过，可使用伴随页按钮，也可使用下列调试指令。
- 自愿说话阶段暂不录音、不识别，可与 Lily 交互或按“跳过这一步”继续。
- 如果走近动物后想再听，退回能同时看到两只动物的位置。页面等待可见性时不会偷偷计播放完成。

```text
/scriptevent farm:help
/scriptevent farm:replay
/scriptevent farm:pause
/scriptevent farm:resume
/scriptevent farm:skip
/scriptevent farm:exit
```

Lily 的继续操作不能绕过听力验证。角色交互键在具体客户端上是否符合幼儿操作习惯，仍需实机确认。
当前 Lily 使用原版村民外观，未制作定制角色模型。

## 音画、恢复与幂等边界

服务端场景检查要求：玩家在线且同维度，目标近距离处于窄视锥，方块射线无遮挡。
听力随机辨认要求两只动物均满足条件；视觉完成绑定当前 command_id。
这属于服务端几何检查，不能检测客户端窗口是否被遮挡、是否最小化，也不能直接观察孩子是否在看。
需要在实际显示设置和 FOV 下校准；未把几何检查宣称为客户端画面验证。

BDS 默认每 4 tick 尝试同步，已有同步未结束时不会再开并发请求。
心跳有效期为 1.5 秒；中断后代次递增，开始于旧代次的音频完成不能计入呈现。
伴随页恢复后会从头重播当前音频，只有实际媒体结束并通过服务端校验才 ACK。
网页失去焦点后可以继续声音，便于在游戏中操作；断开游戏租约或暂停课次才停止当前声音。

动作执行记录最多 128 条并受动态属性大小限制，事件发件箱最多 32 条，超限会明确报错。
随机位置在世界效果前保存，ACK 丢失后沿用同一结果。
门和装饰使用固定坐标的状态赋值，即使效果发生后保存执行记录失败，再执行也不会多发物品。
已播放的瞬时提示在崩溃间隙可能再次出现；没有承诺所有游戏副作用都恰好执行一次。
动态属性的硬崩溃持久性仍取决于 Minecraft 存档，不能等同 SQLite 事务保证。

M3 的游戏内事件共享 game 序号，伴随页控制使用 control 序号，语音使用 voice 序号。
绑定检查、教学事件处理、状态和动作入队仍在 SQLite 同一事务内完成。
普通 Mock 游戏端和旧的游戏动作接口不能读写绑定课次的游戏队列。

## P95 检查

```powershell
$headers = @{}
if ($env:API_TOKEN) { $headers['X-API-Token'] = $env:API_TOKEN }
Invoke-RestMethod 'http://127.0.0.1:8000/v1/bedrock/metrics/farm_m3_01' -Headers $headers
```

只统计本进程从实际选择事件到 `PLAY_FEEDBACK` 执行完成的时间，不包含英语音频长度。
同一个 command_id 只保留一个样本；统计上报失败可在 ACK 后继续重试，不重做游戏效果。
重启后若缺少事件起始时间，不上传零耗时填充样本。
P95 使用最近秩法；没有样本时为 null。目标是 800 ms，`runtime_verified` 始终保持 false，
实际验收应记录原始场景、样本量和实机观察，不能仅凭上报接口判定通过。

## 已完成验证

- Python **81 项通过**：包含首课 M3 路由闭环、H2 支持归因、可选口语跳过、唯一奖励、
  暂停恢复、过期/失效视觉租约、身份隔离、P95 去重、M3 包及安装路径。
- Node **38 项通过**：包含世界效果与 ledger 保存之间崩溃、ACK 丢失重启、随机结果恢复、
  暂停不执行、旧提示过滤、反馈统计重试、媒体结束回执与伴随页存储隔离。
- Ruff、Python 类/方法职责说明、ESLint、Prettier、Minecraft 两套 API 类型检查通过。
- 实际浏览器检查伴随页：连接失败提示、连接恢复、真实欢迎音频、暂停/恢复、继续进入第二步，
  第二步缺少游戏视觉证据时等待播放。未出现 JavaScript 错误。
- 浏览器检查使用独立的 `data/m3-preview.sqlite3` 和**模拟游戏心跳**；测试服务和临时心跳已关闭。
- 仍保留现有 Starlette/HTTPX 的一条弃用警告，未屏蔽。

## 实机仍待验收

- 目标 Bedrock/BDS 版本与候选模块是否真正兼容。
- 农场生成、原生交互、粒子与声音标识是否按预期生效。
- 完整首课的游戏视角、音画同步、操作难度和复习体验。
- 停服/恢复、正常重启与奖励重发的真实世界结果。
- 实机事件到反馈的 P95 是否小于 800 ms。

本次环境检查仍未找到可用的国际版客户端/BDS 组合，因此上述项目未打勾。

## 官方 API 依据

- [实体交互前事件与取消](https://learn.microsoft.com/en-us/minecraft/creator/scriptapi/minecraft/server/playerinteractwithentitybeforeevent?view=minecraft-bedrock-stable)
- [实体视向、视线与传送](https://learn.microsoft.com/en-us/minecraft/creator/scriptapi/minecraft/server/entity?view=minecraft-bedrock-stable)
- [维度射线与方块状态设置](https://github.com/MicrosoftDocs/minecraft-creator/blob/main/creator/ScriptAPI/minecraft/server/Dimension.md)
- [BDS 网络与模块权限](https://learn.microsoft.com/en-us/minecraft/creator/documents/bedrockserver/scripting?view=minecraft-bedrock-stable)
