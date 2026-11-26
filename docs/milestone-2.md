# M2 开发与联调说明

2026-11-26：事件接入代码和离线检查完成，**M2 实机 DoD 尚未通过**。
用户已确定国际版 Minecraft for Windows（Bedrock）+ BDS。
环境检查目前只检出 Minecraft Education 1.26.3300.0，尚未找到国际版客户端与可运行 BDS。
教育版桥接项目未被修改或用于替代原规格。

## 本次实现

- 本地诊断包：主动生成带 `farm:m2` 标签的牛、猪及小麦、胡萝卜，监听成功实体交互。
- BDS 候选包：独立 HTTP 探针、匿名玩家绑定、每秒读取权威任务、标准化交互事件。
- 发件箱：世界动态属性保存原始事件 ID、时间、任务及序号；最多 32 条、单次发送，
  断网指数退避，响应丢失重发原事件，认证/契约错误停发并保留队列。
- 后端：独立 BDS 令牌与实际网络来源限制，世界绑定不可覆盖，课次不能同时接收 Mock 游戏事件。
  SQLite 事务内去重并处理事件。发送端和 API 均要求先有探针成功记录。
- 安装工具：检查目标路径和停机状态，仅扩展指定脚本模块权限，备份已有世界包列表。
- 所有类、方法和具名函数包含职责说明；JS 分支复杂度上限 8，函数长度上限 60 行。

仅测试动物会产生上报；不记录玩家名字、位置、聊天或原始网络响应。
世界内部保存原生玩家实体 ID 用于阻止换人，该 ID 不进入 API 和诊断日志。

## 版本候选与产物

| 包 | Script API 依赖 | 状态 |
| --- | --- | --- |
| `dist/english-farm-m2-diagnostic.mcpack` | `@minecraft/server` 2.0.0；最低引擎声明 1.21.80 | API 类型检查通过，未游戏导入验证 |
| `dist/english-farm-m2-bds-1.26.66-candidate.mcpack` | server 2.11.0，server-net/admin 1.0.0-beta.1.26.66-stable | 候选组合，未 BDS 加载验证 |

候选来自官方 npm 类型包，开发依赖已精确锁定；这不是实机兼容性保证。
manifest 使用当前候选模块版本声明。若 BDS 拒绝这些版本，应根据实际启动日志和对应官方模块
文档更新 `bedrock-pack/profiles.json`，重新构建并实测，不猜测回退版本。
安装脚本只接受 1.26.66 的版本声明；声明本身不会被当成已验证版本。

构建：

```powershell
# 在克隆后的仓库根目录执行。
.\.venv\Scripts\python.exe -X utf8 scripts/build_bedrock.py
```

包中没有令牌；网络包只含当前入口的脚本依赖。诊断包不导入 server-net/admin。
`dist` 为生成目录，可随时通过上述命令重新构建。

## 第一步：本地事件诊断

1. 使用国际版客户端新建专用平坦测试世界，创造模式并启用作弊指令。
2. 导入 `diagnostic.mcpack` 并在该测试世界启用行为包。启用游戏的内容日志。
3. 进入世界，日志应出现 `Diagnostic loaded`。站在空旷平地，执行：

   ```text
   /scriptevent farm:setup
   ```

4. 捡起饲料，持小麦对牛使用交互键、持胡萝卜对猪使用交互键。
5. 保存日志中的 `source/entity_type/player_present/before_item_present/after_item_present`。
   不要保存包含账号信息的整份日志到项目中。

当前监听 `playerInteractWithEntity` 成功后事件；**空手点击是否产生成功事件仍需实测**，
不能把这套饲喂诊断说成最终的“点一下选择”体验。M3 再确定幼儿实际操作方式。
场景仅生成实体，不改地形，不能重复执行来批量复制动物。
若生成过程中发生区块错误，使用新的测试世界重试。不要在常用存档运行诊断命令。

## 第二步：准备 BDS 测试世界

先核对版本，脚本只读取环境：

```powershell
.\scripts\check_m2_environment.ps1 -BdsPath 'D:\MinecraftBDS'
```

`D:\MinecraftBDS` 是示例，必须替换成真实目录。
需要客户端能连接对应 BDS，并有独立的测试世界。
网络候选包需要启用 **Beta APIs** 实验的世界；可在匹配客户端创建并导出该测试世界，
再按 BDS 支持的流程部署到 `worlds`。脚本不会修改 `level.dat` 或开启世界实验。
将 `server.properties` 的 `level-name` 指向该测试世界，启用测试需要的作弊权限，
仅为测试操作者赋予执行 `/scriptevent` 所需权限。
同一测试世界只启用一个本项目包；不要同时启用诊断包与网络包。

## 第三步：启动 API 并安装候选包

终端一：

```powershell
.\scripts\start_m2.ps1
```

使用独立的 `data/m2-progress.sqlite3`，生成并复用 `data/bds-token.txt`。
API 只监听 127.0.0.1，关闭代理头解析。启动窗口保持打开。
`MOCK_MODE` 仍保持默认 true：M2 接入事件，游戏内动作执行属于 M3。

正常停止 BDS 后，在终端二运行：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/configure_bds.py `
  --bds-dir 'D:\MinecraftBDS' --world-name 'Farm M2' `
  --bds-version '1.26.66' --bridge-id 'farm_m2_01'
```

如果设置过 `API_TOKEN`，两个终端应使用同一个操作员令牌。
工具会创建一个 READY 匿名诊断课次，安装到 `behavior_packs/english_farm_m2`，
将权限、URL 和秘密放入 `config/<script UUID>/`，不会修改全局 `config/default`。
世界已有包列表备份为 `world_behavior_packs.before-m2.json`。
已有 M2 安装不会被覆盖。新世界/新课次应使用独立的 BDS 测试目录及新的 bridge ID。
私有配置、数据库和令牌均留在忽略的 `data` 或用户 BDS 目录，不应加入仓库。

## 第四步：真实 HTTP 门槛

启动 BDS，确认日志无模块/权限错误，出现 `BDS candidate loaded` 后，用国际版客户端加入。
在游戏内依次执行：

```text
/scriptevent farm:setup
/scriptevent farm:probe
```

收到 HTTP probe passed 后执行：

```text
/scriptevent farm:bind
```

再分别给牛和猪喂食。每次成功交互应出现匿名原生事件日志。
操作员终端查看后端：

```powershell
$headers = @{}
if ($env:API_TOKEN) { $headers['X-API-Token'] = $env:API_TOKEN }
Invoke-RestMethod 'http://127.0.0.1:8000/v1/bds/status/farm_m2_01' -Headers $headers
```

- `http_received=true`：服务端收到过探针，不等于游戏事件已通过。
- `interaction_receipts`：该绑定的唯一交互收据数，包括被教学状态安全忽略的交互。
- `gameplay_verified=false`：软件不会用一次 HTTP 请求自动宣称实机验收通过。

诊断课次故意保持 READY，交互结果应为 `ignored_not_started`，但真实事件收据会增加。
这是 M2 的传输测试，不产生学习分数。不要用浏览器补发视觉或播放回执来伪造游戏教学闭环。

暂停 API 后继续观察：已排队事件保留；上下文超过 5 秒后不再接收新选择，不猜测任务。
恢复 API 后应重发原事件。出现 `HTTP_RETRY_OR_HALTED_CHECK_API` 时检查 API、令牌及契约，
修复后再运行 `farm:probe`。BDS 重启后也需要重新探针，世界和玩家绑定及发件箱则从存档恢复。
队列满时明确报错，保存原事件，不静默丢弃。世界动态属性的硬崩溃持久性仍取决于游戏存档，
不能声称像 SQLite 一样在断电时具备事务保证。

## 实机退出条件（仍待执行）

- 记录实际客户端、BDS、三个模块版本及测试日期。
- 两只动物的真实原生事件字段均符合契约，API 唯一收据增加。
- 禁用网络权限或停止 API 时不伪造成功、不影响 M1 Mock 演示。
- API 恢复/正常重启 BDS 后未确认事件可恢复，重复事件不会重复处理。
- 非绑定玩家、旧任务、错误世界及普通 Mock 通道均不能推进绑定课次。

通过后将真实版本、脱敏日志片段及结果写入本文件，再勾选任务表中的实机项。
M3 才实现随机位置呈现、实际语音同步、游戏提示、奖励与完整课程串联。

## 本次已运行的检查

- Python：71 项通过；覆盖 BDS 认证、探针、不可覆盖绑定、错玩家/任务、幂等恢复、包隔离与安装边界。
- Node：25 项通过（M1 17 项、M2 8 项）；覆盖响应丢失、旧事件、过期上下文、队列满、并发发送及探针失败。
- Ruff、Python 职责注释、ESLint、Prettier 均通过。
- 网络包按 server 2.11.0 类型检查；诊断包另按 server 2.0.0 类型检查，均通过。
- 导出的 OpenAPI 与运行时契约一致。
- 实际启动 `start_m2.ps1 -Port 8766`，检查 loopback HTTP 健康、正确/错误 BDS 令牌及代理头隔离；
  检查后关闭测试服务。这只验证本机 API 启动，不代表 BDS 发起了请求。
- 保留一条现有 Starlette/HTTPX 弃用警告；未屏蔽，也未影响通过结果。

这些是离线代码/协议测试，没有使用 Minecraft 运行时来验证加载或网络。

## 官方依据

- [BDS 专用网络模块及预发布边界](https://learn.microsoft.com/en-us/minecraft/creator/scriptapi/minecraft/server-net/minecraft-server-net?view=minecraft-bedrock-experimental)
- [BDS 脚本权限、模块独立配置及秘密](https://learn.microsoft.com/en-us/minecraft/creator/documents/bedrockserver/scripting?view=minecraft-bedrock-stable)
- [成功实体交互事件字段](https://learn.microsoft.com/en-us/minecraft/creator/scriptapi/minecraft/server/playerinteractwithentityafterevent?view=minecraft-bedrock-stable)
- [官方 BDS 下载与运行入口](https://www.minecraft.net/en-us/download/server/bedrock)
