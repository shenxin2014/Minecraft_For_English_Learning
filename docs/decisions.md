# 开发准备：规格缺口与 M0 实现决定

原始 V1.1 文档已原样复制到本目录。原文提到的 AGENTS.md、完整课程 JSON、OpenAPI
附件未在已检查目录顶层找到。本项目对应文件是根据正文补建的开发产物，不声称为原附件。

## P01：完整首课配置

顺序为入口探索 → 牛介绍 → 猪介绍 → 找牛 → 找猪 → 草地找回牛 → 自愿说 cow →
自由探索 → 换围栏复习 pig → 换围栏复习 cow。只有 cow、pig 是新目标词。
最后两次复习分别生成任务，使两词都有观察机会；这是对原文随机结尾复习的具体化。
时间不作为强制任务门槛。第一课不包含 sheep、拼读或发音评分。

## P02：统一事件和动作契约

- 使用 `kind` 作为内部事件类型。游戏端额外接受原文的 `event_type` 别名。
- 所有状态变更事件包含 `event_id/session_id/player_id/task_id/sequence`。
- 语音事件增加原文精简示例未列出的玩家与序号，以便归属校验。
- `sequence` 在每个 session 的 game / voice / control 来源内严格递增；START 属于 control。
- 全局 `event_id` 唯一。相同内容重试返回第一次结果并标记 `duplicate=true`；
  不同内容复用同一个 ID 返回 409。读取最新进度需另行 GET，会话不会被历史响应回滚。
- 错玩家、错任务、过期序号、超过服务端 5 分钟的未来时间记录后忽略。
  客户端可不发送 `occurred_at`，服务端单独记录实际接收时间。
- `VISUAL_READY` 与 `LAYOUT_READY` 必须关联当前视觉命令的 `command_id`。
  `LAYOUT_READY` 表示适配器完成随机位置安排且目标可见；单纯可见不等同于随机化。
- `AUDIO_FINISHED/AUDIO_FAILED` 必须关联当前播放命令。旧播放回执不能推进新播放。
- 指令采用每个 command 一个动作的队列记录，不采用原文示例的 actions 数组。
  多个奖励仍可在同一事务入队，每个动作分别确认。
- 语音通道新增 `PLAY_AUDIO/STOP_AUDIO`，不扩展 Minecraft 游戏动作白名单。
- `/v1/game/actions` 与 `/v1/voice/actions` 共享带 audience 参数的路由实现。
  动作 ACK 用 command_id 幂等；失败 ACK 保留 pending，错误通道 ACK 返回 404。
- 课程配置使用 target=`cow/pig`，GameAdapter 对应到 `minecraft:cow/pig`。
  契约以自动生成的 `contracts/openapi.yaml` 为准。

## P03：状态、恢复与提示

整个 Session 包含当前 task_index，状态表示当前步骤所处阶段。
VERIFIED 为事务内的短暂确认状态，确认后立即开始下一任务；只有最后一个任务结束才是 COMPLETE。

- OBSERVE / EXPLORE 播放完毕后等待 CONTINUE，不假设孩子必须做游戏选择。
- LISTEN_FIND 等待游戏选择，错误目标保留当前任务；成功后记录证据并推进。
- OPTIONAL_SPEAK 可识别一次非空发言，也可 SKIP；不判断发音质量和词汇掌握。
- HELP 依次进入 H1–H4；H4 不再升级。H1 请求重播，其余发出对应级别的提示意图。
  M0 只验证意图与归因，实际动物叫声、高亮和带路由后续客户端/行为包实现。
- TIMEOUT 先按操作障碍处理，不自动提升英语提示；OPERATION_READY 后才恢复接受选择。
- SKIP 可随时跳过活动任务，无该任务奖励；可提前 EXIT。
- PAUSED / EXITED 保存原状态并签发 STOP_AUDIO，不接受普通教学事件。
  RESUME 回到原状态；若仍在 INTRODUCING，则签发新的播放 ID。
- 暂停会取消尚未执行的旧音频。任务切换会取消旧提示，但保留已经确认的奖励。
- 进程重启从 SQLite 直接恢复最新已提交状态，不重做已完成任务。
  客户端需要保存 session_id，之后 GET 查询。不存在假装“自动识别孩子”的身份逻辑。

## 教学证据

音频完成与视觉回执可以任意顺序到达；两者齐备才计一次输入机会。
同一播放的重复回执不增加次数，成功重播可增加呈现机会。
播放失败不计有效呈现，并使后续成功至少归入 H1 支持。

独立正确要求 H0、首次选择和已确认随机布局。先点错后点对或未确认随机布局的正确结果，
记入 `unconfirmed_correct`，不会虚增独立正确。
不同场景的再次独立成功记为 `transfer_correct`。
默认 3 次独立成功才进入 UNDERSTANDS，属于可调整实验阈值。
M0 从不设置 stable_mastery=true，跨日期的 RETENTION_CHECK 和复习调度在 M5 实现。

## P04：故障分层

| 故障 | M0 行为 | 后续验证 |
| --- | --- | --- |
| 云端语音不可用 | OFFLINE_FALLBACK，继续非口语任务 | M4 真实服务断网测试 |
| 本地音频不可播放 | 不计呈现，进入提示路径，可继续或跳过 | M1 播放器测试 |
| 客户端到 API 断开 | 数据持久化，重连后 GET 状态、重试未确认事件 | M1/M4 客户端重连 |
| BDS 到 API 断开 | 不假定新任务可以离线判分或发奖励 | M2/M3 验证缓存任务/自由探索策略 |
| API 进程退出 | 已提交进度保留，未提交事务全部回滚 | M0 已覆盖重建应用与回滚 |

本阶段“离线”指不依赖互联网和云端服务，课程引擎本身仍需运行。
不会把“云端断网可继续”错误扩展为“API 不运行也能推进全部课程”。

## P05：验收映射

T01–T12 的离线版本位于 `backend/tests/test_acceptance.py`。
补充边界位于 `backend/tests/test_boundaries.py`。
Mock 全流程不等于 M2 的 Windows/BDS 实机验收；实际音频、动物交互和耗时测量分别后移到 M1–M4。

## 原子性与投递语义

BEGIN IMMEDIATE 事务包裹状态、事件结果和动作入队。SQLite 写锁串行化并发事件。
动作轮询采用至少一次投递，ACK 丢失时可能重投；真实 GameAdapter 必须提供幂等映射。
Mock 把效果和 command_id 放在独立 SQLite 事务中，验证重启和重投时不会重复产生模拟效果。
这不构成对真实 Minecraft 副作用恰好执行一次的承诺。

## M2：独立事件入口与兼容性门槛

BDS 输入单独经过 `/v1/bds/*` 的受限端点，使用专用令牌及 TCP 来源白名单。
操作员以新 READY 课次建立不可变世界绑定；普通 `/v1/game/events` 无法向该课次写入。
绑定检查与学习事件处理处于同一 SQLite 事务，BDS 不能以视觉回执或任意命令越权。

网络候选包必须先取得 HTTP 探针收据。真实事件仍使用原有 game 序号和幂等规则。
发件箱保存事件发生时的任务，重试不会把旧点击重新归入新任务。
HTTP 探针、诊断事件收据与教学判定分别报告；M2 不生成视觉、布局或播放完成证据。
当前包与模块版本仅是候选，详细实机门槛见 `milestone-2.md`。

暂停前已被播放器取走的音频无法被 HTTP 服务器撤回；客户端必须落实 STOP_AUDIO，
并在恢复播放前检查最新会话状态。M0 验证的是命令取消和回执隔离。
