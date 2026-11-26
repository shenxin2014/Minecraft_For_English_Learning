# Minecraft AI 英语启蒙教学系统

> **教学设计 + 产品需求 + Codex 开发规格（V1.1）**  
> 编写日期：2026-11-24｜目标平台：Minecraft Bedrock Edition + Windows 语音客户端  
> 状态：**可用于原型开发，不代表所有游戏通信接口已通过实机验证**

## 执行摘要

本项目面向 **6 岁左右、英语零基础或接近零基础儿童**，以 Minecraft 为交互场景，采用“**可理解输入 → 情境重复 → 游戏动作理解 → 分级提示 → 间隔复习 → 自愿口语**”的课程结构。孩子通过**听懂英语来推进游戏**，而不是为了游戏而被迫作答。

首期交付一个 15–20 分钟的 **English Farm（英语农场）**，仅教授 `cow` 和 `pig` 两个新目标词，复用 `Look!`、`Find the…` 等短指令；第二节再加入 `sheep`。教师 NPC 名称为 Lily。游戏内负责场景、目标与反馈，外部语音客户端负责实时听说，课程引擎负责教学判断。**实时语音识别失败不得导致游戏被锁死。**

**本文件同时是 Codex 的开发任务基准。** 文末包含目录结构、事件契约、课程配置、状态机、验收测试、分阶段工单和可直接粘贴给 Codex 的启动指令。附带的 `AGENTS.md`、`lesson_farm_01.json`、`openapi.yaml` 提供机器可读入口。

---

# 1. 产品边界与成功定义

## 1.1 用户、设备与约束

| 项目 | 约束 |
|---|---|
| 年龄 | 以 6 岁为首批用户，面向 5–8 岁拓展 |
| 英语起点 | 零基础 / 认识零散单词，不假定能独立阅读英文 |
| 设备 | Windows 电脑、键鼠、麦克风、耳机或音箱 |
| 游戏 | 国际版 Minecraft Bedrock，使用专门教学地图 |
| 教学节奏 | 每次 15–20 分钟；可中途暂停、重听和退出 |
| 成人参与 | 第一周建议家长陪同操作，之后逐渐减少协助 |
| 分发 | 首期单机家庭原型，不做商业化或公开多人联机 |

## 1.2 产品必须做到（Must Have）

1. 用英文短语对**可见的物体或动作**提供同步输入，并支持重听。
2. 一个词在**稳定句型、不同动作和不同场景**中自然复现；不根据播放次数直接判定掌握。
3. 孩子通过点击、靠近、寻找等动作表明理解，不强制说英语。
4. 能区分**有提示完成**与**无提示完成**；随机碰对不能过早晋级。
5. 教学引导与 Minecraft 任务绑定，保留受控探索及自由建造时间。
6. 课程状态、奖励和进度由**确定性引擎**控制，不由大模型直接决定。
7. 支持 AI 实时听说，但网络或语音服务不可用时能使用**预录音 + 非语音任务**继续。
8. 记录最少必要的学习数据；具备家长同意、录音提示和删除机制。

## 1.3 首期不做（Non-goals）

不做自由开放世界英语聊天、复杂语法、自动判定儿童 CEFR、完整拼读体系、教师 SaaS 管理后台、多人课堂、商业支付、强制发音评分、未经审核的 AI 自动造题、动态语音直接写入 Minecraft NPC 3D 音频。

## 1.4 判断产品是否有效

**不能只看**：游戏在线时长、音频播放次数、勋章数、总答题数。  
**应该观察**：无提示听力选择、隔日复现、换场景识别、需要提示的类型、主动要求重听、自愿开口、儿童愉悦度与疲劳迹象。所有初期指标都是探索性指标，不对学习效果作保证。

---

# 2. 教学设计：课程目标和认知负荷

## 2.1 六条不可破坏的教学原则

1. **输入先于输出**：先听、看、操作，之后自愿模仿；口语不是 L0/L1 过关条件。
2. **可理解输入**：首次输入需与动物、视觉突出、声音或动作同步；避免只播抽象句子。
3. **稳定中小变**：先固定 `Find the cow.`，后换位置、干扰项、背景；再换句型。一次只提高一个主要难度因素。
4. **重复而不机械**：跨行为、情节、日期复现；当已理解时减少冗余，遇困难时改变支架而非无限播放。
5. **语言难度与游戏操作难度分离**：英文不熟时操作应简单；操作困难不算英语错误。
6. **安全与自主**：允许重播、求助、安静玩、跳过和提前结束。无倒计时恐吓、不因发音差扣分。

## 2.2 两条学习线

**词汇线（Vocabulary Track）**：`cow → pig → sheep → colors → numbers → actions → objects`。  
**表达线（Pattern Track）**：`Look! → This is a… → Find the… → Go to the… → Where is the…? → Get two…`。

第一课专门验证词 `cow / pig`。`Look!` 和 `Find the…` 由动作和画面支撑，可多次输入，但不把整句所有词列为一次性“已掌握词”。第二课复习 cow/pig 后引入 sheep；自然拼读另设短时线，不以 cow/sheep 作为最早的 CVC 拼读例词。

## 2.3 内部能力等级（不是标准 CEFR）

| 等级 | 听力理解目标 | 游戏响应 |
|---|---|---|
| L0 | 音形对应，知道正在介绍哪种动物 | 注视/跟随、可不互动 |
| L1 | 辨别两个熟悉目标词 | 在两项中选择 |
| L2 | 理解固定指令 `Find the …` | 在三项中找目标 |
| L3 | 理解颜色/数量与物品组合 | 选 `red door` / `two apples` |
| L4 | 执行简单两步指令 | 先找再带回 |

游戏操作维度独立记作 G0 观察、G1 点击、G2 移动、G3 收集、G4 建造。MVP 主要使用 G0–G2。

## 2.4 学习时段建议

单节 15–20 分钟，其中大部分是**听、看、操作**。2–3 秒的单词/短句与数秒至数十秒的游戏行为交替出现，不做无休止的英语播报。首次三次输入不连续堆叠；让孩子有时间观察并动手。默认不强制开口。单个新词当日的呈现次数是调整参数，不是固定教学指标。

---

# 3. 输入、理解、提示、复习的标准循环

## 3.1 六阶段课内循环

| 阶段 | 目的 | 例子 | 记录 |
|---|---|---|---|
| A 场景呈现 | 建立词义 | 牛高亮；Lily：`Look! A cow!` | audio_started、visual_anchor |
| B 有意义复现 | 巩固声音 | 牛吃草时：`A cow!` | exposure、context |
| C 引导理解 | 在有帮助时行动 | `Find the cow.` + 轻提示 | assisted_attempt |
| D 独立理解 | 判断是否听懂 | 取消高亮，随机换位选择 | independent_attempt |
| E 小幅迁移 | 避免记位置 | 换一个围栏、保留句型 | transfer_attempt |
| F 复习安排 | 检查保留 | 次日或稍后再出现 | review_due |

## 3.2 提示阶梯（Scaffolding）

| 级别 | 行为 | 数据解释 |
|---|---|---|
| H0 | 仅播放自然语速的短指令 | 无提示独立测试 |
| H1 | 再播放一次、略减速 | 语音重复支持 |
| H2 | 增加自然声或动作线索（牛叫声） | 有提示完成 |
| H3 | 突出显示目标一小段时间 | 明显提示 |
| H4 | Lily 带路/展示选择 | 教学演示，不计独立掌握 |

超过预设时间无响应，先检查是否卡住键鼠操作；不要盲目升级英语提示。每次失败允许重来或跳过，最后要保留积极反馈。

## 3.3 “理解”证据与评价口径

- `exposure_count`：完成播放且视觉锚点可用的呈现次数，仅说明**机会存在**，不能证明听见。
- `assisted_correct`：存在 H1–H4 任一提示后正确完成。
- `independent_correct`：H0 状态下首次正确选择，且对应目标位置随机化。
- `transfer_correct`：换背景、位置或不同日期后的独立成功。
- `operational_block`：因键鼠、路径等操作能力导致未完成；**不得记为英语错误**。
- `guess_risk`：使用多个目标、位置打乱、多轮复现降低碰巧选择的解释力。

词汇状态 `UNSEEN / INTRODUCED / PRACTICING / UNDERSTANDS / RETENTION_CHECK`。提升到 `UNDERSTANDS` 需要跨多次独立辨认；稳定掌握只在跨日期/场景复核后记录。阈值作为可配置实验参数，禁止声称为标准化诊断。

## 3.4 口语与自然拼读

- 早期口语 `OPTIONAL`：Lily 可说 `Can you say cow?`，选择“说一说 / 再听 / 继续”三种路径，孩子沉默仍可进入下一步。
- 实时对话在孩子主动交谈时启用，句子短、一次只问一个问题，不能凭 AI 自由判断“学会”。
- 发音评估与理解分开存储，不能把语音识别失败当作发音差；不给 6 岁儿童严苛统一分数门槛。
- 另设短时音素与字母对应活动，选择规则拼读的入门音素/词，不从复杂拼写的 cow、sheep 开始。

## 3.5 家庭迁移

完成农场后，家长可用真实动物图片或绘本进行 2 分钟 `Where is the cow?` 游戏；不强制、不要求上传儿童照片。复习结果可由家长选择“能认出/需要提示/未练习”。

---

# 4. 样板课程：Unit 1 · My Little Farm

## 4.1 故事与目标

故事：Lily 的农场中有一头牛和一头猪。先参观动物，再帮助找回走出围栏的牛。孩子因“听懂了英语”而改变世界。首节仅新增两个目标词 `cow`、`pig`；下一节才加入 sheep。

- **语言目标**：建立 cow/pig 声音与动物对应；开始理解 `Look!`、`Find the…`。
- **游戏目标**：点击或靠近目标动物、完成一次小剧情、自由探索。
- **非目标**：拼写 cow、流利对话、发音打分、识读长英文说明。

## 4.2 18 分钟逐段脚本

| 时段 | 世界状态 / Lily 语音 | 孩子行为 | 系统验证 |
|---|---|---|---|
| 00:00–02:00 | 农场入口，安静探索；Lily 简短欢迎，不考试 | 熟悉键鼠、观察动物 | 操作异常可启用家长模式 |
| 02:00–04:00 | 只突出牛：`Look! A cow!`；牛走动后：`A cow!` | 观察/接近牛 | 记录输入机会，不评分 |
| 04:00–06:00 | 只突出猪：`Look! A pig!`；猪活动后：`A pig!` | 观察/接近猪 | 记录输入机会 |
| 06:00–08:00 | Lily：`Find the cow.` 两目标可见；首次可提供提示 | 选择牛 | 计 assisted 或 independent |
| 08:00–10:00 | Lily：`Find the pig.` 动物位置打乱 | 选择猪 | 提示级别与操作障碍 |
| 10:00–13:00 | 小故事：牛离开围栏。Lily：`Oh! The cow! Find the cow.` | 在草地寻找并点击牛 | 事件 + 当前任务双重校验 |
| 13:00–15:00 | Lily：`The cow is home!`；邀请：`Can you say cow?` | 可跟读、可重听、可跳过 | 口语参与可选，不阻塞 |
| 15:00–17:00 | 开放短时自由照顾动物，偶尔简短场景描述 | 喂养/观察/建造装饰 | 不频繁插话、不强行提问 |
| 17:00–18:00 | 无高亮复习：随机目标 `Find the pig/cow.` | 无提示选择 | 记录理解状态、结束 |

**时间为教案规划，不是不可跳过的固定计时**。孩子若提前完成，可留更多自由探索；困难时降低任务密度或提前结束。

## 4.3 语音与画面同步约束

- 教学音频 `A cow!` 播放时，牛必须处于可见区域，画面有轻微视觉指向。
- 不能在孩子正在操作危险或复杂路径时突然播放长指令。
- 不向零基础孩子同一时刻引入多个陌生词，允许小幅自然变体，但固定核心语义。
- 音频不能正常播放时显示图标，支持家长点击重播；未播放成功不计有效呈现。
- 实时生成的语音通过外部 Windows 客户端播放，不承诺 Minecraft 原生 NPC 空间化实时语音。

## 4.4 课程完成标准

孩子获得**游戏剧情完成**（找回牛）与**学习观察结果**（词汇理解记录）两个独立结果。即使需要 H4 提示完成，剧情也可正常结束；报告明确写“需要提示”，而非“掌握”。奖励不以发音分数绑定。

---

# 5. AI 教师行为规范

## 5.1 两个引擎各司其职

- `LessonEngine`：确定**当前目标、允许的任务、何时重播、提示阶梯、如何评分、下一关**。这是唯一的教学状态权威。
- `AITeacher`：在给定目标与允许语句/词汇内**朗读、重述、解释、鼓励、回应孩子**。不得直接授予奖励、改分或执行游戏命令。

## 5.2 对话行为约束

1. 一次一条短消息、一个问题；零基础优先 2–6 个英文词的指令。
2. 新词出现必须有游戏视觉/动作锚点或已熟悉的支持语境。
3. 允许孩子保持沉默、使用中文求助、要求重听。
4. 不责备、不打分恐吓、不说“你怎么还不会”；识别不确定时先重听。
5. AI 产生的建议动作必须经过 `AllowedAction` 白名单校验。
6. AI 自由聊天不得把教学目标替换成未经审核的内容；偏离后自然引导回故事。
7. 不主动询问或保存儿童姓名、家庭地址、学校等身份信息。

## 5.3 三种语音模式

| 模式 | 使用时机 | 实现 |
|---|---|---|
| `PREGENERATED` | 固定词和固定课堂指令 | 预生成音频 + 资源包或音频缓存 |
| `GUIDED_REALTIME` | 口语尝试、询问原因、重述提示 | 实时语音 AI，仅围绕当前任务 |
| `OFFLINE_FALLBACK` | 断网、配额不足、设备无麦克风 | 播放缓存语音，继续非口语任务 |

首期开发可以先实现 `PREGENERATED + OFFLINE_FALLBACK` 的完整课程，然后接入 `GUIDED_REALTIME`，避免 AI 语音阻塞核心教学闭环。

---

# 6. 系统架构与技术可行性边界

## 6.1 目标部署

```text
Windows Minecraft Bedrock Client
       ⇅  游戏协议
Bedrock Dedicated Server（BDS）
       │ Behavior Pack + @minecraft/server 事件
       │ GameAdapter（HTTP / 可替换桥）
       ⇅
Python FastAPI ── LessonEngine / ExposureEngine / ReviewScheduler / ProgressRepo
       ⇅                                  ⇅
Electron Voice Client                 SQLite
       ⇅
Realtime Speech Provider（可替换：Mock / Azure / 其他）
```

**重要边界**：微软官方的 `@minecraft/server-net` **仅用于 Bedrock Dedicated Server**，不能在普通 Bedrock 客户端/Realms 使用；官方仍标注为**预发布**，具体版本依赖必须以所安装的 BDS 版本为准。不得在未实测之前承诺其 HTTP 网络通信在所有版本可用。若不可用，先运行 `MockGameAdapter`，然后研究受支持的 BDS 版本或替代通信桥，不要默默使用未经验证的私有协议。

## 6.2 推荐模块和职责

| 模块 | 职责 | 技术 |
|---|---|---|
| `bedrock-pack` | 游戏事件、奖励、目标区域、简单 UI | JS/TS + Behavior Pack |
| `GameAdapter` | 标准化事件、幂等接收、动作执行 | TS + HTTP 或 Mock |
| `api` | 会话、课程配置、任务事件与报表 API | FastAPI / Pydantic |
| `LessonEngine` | 确定性状态机，判断过关 | Python |
| `ExposureEngine` | 输入规划、同步、重复和提示 | Python |
| `ReviewScheduler` | 复习建议；初期规则式 | Python |
| `voice-client` | 麦克风、音频播放、录音状态 | Electron / TS |
| `SpeechProvider` | STT/TTS/实时对话抽象 | Mock 优先，后接厂商 |
| `ProgressRepo` | 学习事件和词汇状态 | SQLite |

## 6.3 技术风险清单（必须逐一验证）

| 风险 | 当前状态 | 验证 / 退路 |
|---|---|---|
| BDS 访问外部 HTTP | 官方预发布，仅 BDS | 实机 P0 测试；失败时保持 Mock |
| 游戏事件名称/字段 | 官方文档支持部分事件 | 锁版本并用最小事件例子实测 |
| NPC 动态音频流 | 非 Minecraft 通用能力 | Windows 语音客户端播放 |
| 语音识别儿童发音 | 供应商能力不保证对所有儿童可靠 | 可重播、跳过、容错、家长辅助 |
| 客户端与 BDS 时间同步 | 自定义协议责任 | 服务端时间戳 + 会话状态 + 事件序号 |
| 断线后任务重复奖励 | 高风险逻辑问题 | `event_id` 去重、任务锁、状态持久化 |
| 地区与许可限制 | 与账号/地区有关 | 开发前确认合法可用的 Bedrock/BDS 环境 |

---

# 7. Codex 可执行的数据契约

> 以下 JSON 是**项目自定义协议**，不是 Minecraft 或 AI 服务已有的原生字段。不要把 `ENTITY_INTERACTED` / `OPEN_GATE` 误认作微软 API。

## 7.1 课程配置（精简示例）

```json
{
  "lesson_id": "farm_01",
  "version": "1.1.0",
  "language_level": "BEGINNER_ZERO",
  "target_vocabulary": ["cow", "pig"],
  "known_patterns": ["Look!", "Find the {target}."],
  "speaking_policy": "OPTIONAL",
  "tasks": [
    {
      "task_id": "find_cow",
      "type": "LISTEN_FIND",
      "prompt_id": "find_cow_en",
      "target": {"entity_type": "minecraft:cow"},
      "check": {"event_type": "ENTITY_INTERACTED", "independent": true},
      "hint_steps": ["REPEAT_AUDIO", "PLAY_ANIMAL_SOUND", "HIGHLIGHT_TARGET", "SHOW_ROUTE"],
      "success_action": "UNLOCK_GATE_01"
    }
  ]
}
```

附带 `lesson_farm_01.json` 是更完整、可解析的首课配置。必须使用 Pydantic 校验 `lesson_id`、`task_id` 唯一性、动作白名单及提示顺序；不允许 AI 运行时直接改写原始课程 JSON。

## 7.2 游戏事件：Minecraft → FastAPI

```json
{
  "event_id": "f4e58d24-e0f4-4f6d-a431-61a3aa33c3da",
  "session_id": "sess_demo_001",
  "player_id": "local_player_01",
  "task_id": "find_cow",
  "event_type": "ENTITY_INTERACTED",
  "entity_type": "minecraft:cow",
  "occurred_at": "2026-11-24T08:00:00Z",
  "sequence": 15
}
```

`event_id` 必须去重；只允许属于当前 session、当前 active task 的事件更新状态。对迟到/重复/未来任务事件记录并安全忽略。玩家 ID 不要直接映射到孩子真实姓名。

## 7.3 服务端动作：FastAPI → GameAdapter

```json
{
  "command_id": "cmd_001",
  "session_id": "sess_demo_001",
  "task_id": "find_cow",
  "actions": [
    {"type": "PLAY_FEEDBACK", "audio_id": "great_cow_en"},
    {"type": "UNLOCK_GATE", "target_id": "gate_01"}
  ]
}
```

动作白名单：`PLAY_FEEDBACK`、`SHOW_HINT`、`HIGHLIGHT_ENTITY`、`UNLOCK_GATE`、`GRANT_COSMETIC`、`SHOW_TITLE`。**不接受 LLM 自由生成的原始 Minecraft 命令。** 只有 `GameAdapter` 内部映射到受审查的游戏 API/命令。

## 7.4 语音事件：Voice Client → FastAPI

```json
{
  "event_id": "e11c6c79-c2ac-41e1-8284-bf52f0904321",
  "session_id": "sess_demo_001",
  "task_id": "optional_say_cow",
  "kind": "SPEECH_RECOGNIZED",
  "transcript": "cow",
  "provider": "mock",
  "request_replay": false
}
```

语音输入只对 `OPTIONAL_SPEAK` 等明确允许的状态生效。不要仅靠转录文本给课程主目标发放奖励。原始音频默认不持久化。

## 7.5 状态机与转移

状态：`READY → INTRODUCING → AWAITING_GAME_ACTION → HINTING → VERIFIED → OPTIONAL_SPEAK → COMPLETE`，任何时刻可以 `PAUSED` 或 `EXITED`。

- `READY + START` → `INTRODUCING`；选择合适语音并同步视觉对象。
- `INTRODUCING + AUDIO_FINISHED` → `AWAITING_GAME_ACTION`；不存在音频时进入有提示降级方案。
- `AWAITING_GAME_ACTION + WRONG_TARGET` → 记录失误、保留当前任务。
- `AWAITING_GAME_ACTION + HELP_REQUESTED/TIMEOUT` → `HINTING`；下一层提示。
- `AWAITING_GAME_ACTION + VALID_EVENT` → `VERIFIED`；仅一次发奖励。
- `VERIFIED + SPEAK_OFFER` → `OPTIONAL_SPEAK`；允许跳过。
- `OPTIONAL_SPEAK + SKIP/SPEECH_DONE` → `COMPLETE`。
- `PAUSED` 时不自动发新语音；恢复时可重播但不得重复加分。

`VIDEO_GAME_TASK_COMPLETE` 与 `VOCAB_MASTERY` 为**独立数据字段**，不共享单一布尔值。

## 7.6 HTTP API（具体请求和响应见 openapi.yaml）

| 接口 | 用途 |
|---|---|
| `POST /v1/sessions` | 创建本地教学会话，加载课次 |
| `GET /v1/sessions/{session_id}` | 读取当前任务、提示级别、状态 |
| `POST /v1/sessions/{session_id}/start` | 开始课程 |
| `POST /v1/game/events` | BDS/Mock 游戏事件上报 |
| `GET /v1/game/actions?session_id=...` | GameAdapter 拉取待执行动作；可先轮询 |
| `POST /v1/game/actions/{command_id}/ack` | 动作执行确认 |
| `POST /v1/voice/events` | 识别、重听、跳过等语音事件 |
| `POST /v1/sessions/{session_id}/control` | pause/resume/help/skip/exit |
| `GET /v1/progress/{session_id}` | 可读学习汇总（不含原始音频） |
| `GET /health` | 服务与模拟适配器状态 |

避免首版同时做复杂 WebSocket 双向推送；先用 REST + 动作轮询证明正确性，再根据延迟需要升级为 WebSocket。所有状态变更请求须包含 `event_id` 或命令 ID 以支持幂等。

---

# 8. 非功能、隐私、安全与可观测性

## 8.1 性能与稳定性（目标值，不是供应商保证）

- 教学事件到游戏反馈：本地条件下目标 P95 < 800 ms（含拉取延迟，不含 TTS 生成）。
- AI 语音：希望话音结束后 1–2 秒开始反馈，实测后再定 SLA。
- 事件处理：同一 `event_id` 重发 3 次，状态只更新 1 次、奖励只发 1 次。
- 网络失联：游戏可继续玩固定语音任务；实时语音提示“现在可以继续听和玩”。
- 课次恢复：应用退出重进后能从上一项已确认任务恢复，重复音频不影响成绩。

## 8.2 儿童隐私

家长同意后才启用麦克风；界面有持续可见的录音指示；仅收集完成教学所需事件。默认不保存原始语音、真实姓名、学校或地理位置；提供本地清除记录功能。外部语音服务接入前，完成服务商未成年人数据处理政策、地区合规、密钥与日志的检查。密钥保存在服务端环境变量中，不写入行为包或前端。

## 8.3 安全与调试

- FastAPI 首期仅监听本地可信网络；BDS↔API 使用共享令牌/受限网络并限制来源。
- `GameAdapter` 只执行课程动作白名单，避免任意 `runCommand`。
- 日志记录 session、task、event、状态转移、耗时和错误码，不输出孩子原始录音、完整自由对话或 API 密钥。
- 所有 AI 输出使用适龄、短句和主题范围约束；超范围内容提供安全、简短的回退文本。

---

# 9. 验收测试与评估设计

## 9.1 自动化测试（必须）

| ID | Given / When / Then | 预期 |
|---|---|---|
| T01 | 课程加载时存在重复 `task_id` | 拒绝配置并给出可定位错误 |
| T02 | 同一游戏事件提交两次 | 只计一次成功，只发一份奖励 |
| T03 | 发送非当前任务的 cow 事件 | 不推进、不发奖励 |
| T04 | H0 条件下首次点击正确 | 记录 `independent_correct` |
| T05 | H3 高亮后点击正确 | 只记录 `assisted_correct` |
| T06 | 玩家卡路时主动请求操作帮助 | 不记录听力错误 |
| T07 | 语音服务宕机 | 无需开口仍能完成课次 |
| T08 | 口语可选环节点击跳过 | 正常结束，无惩罚 |
| T09 | 课次暂停后音频触发 | 不播放新教学语音 |
| T10 | 退出后重新打开 | 从已确认任务恢复且奖励不重复 |
| T11 | 游戏无连接时启动模拟模式 | 用 Mock 事件完成完整课程 |
| T12 | LLM 传入危险或未知动作 | GameAdapter 拒绝执行 |

## 9.2 亲子试用观察

第一轮以**小样本可用性研究**为主，不宣称教学法已获证实。孩子完成第一课后，隔日/数日使用位置不同、无高亮的目标辨认，观察是否存在保持与迁移。记录家长协助、误操作与听力困难，避免混淆。家长可以停止试用或删除数据。

**首课成功验收**：能完整体验一段 15–20 分钟课程；听力任务可在无口语条件下推进；正确/错误/提示/复习事件可靠记录；与 NPC 语音互动在启用时可用，断网可回退；至少一个跨场景复习流程可运行。

---

# 10. Codex 开发路线与任务拆解

## 10.1 建议仓库结构

```text
minecraft-ai-english/
├── AGENTS.md
├── README.md
├── docs/
│   └── Minecraft_AI_英语启蒙教学与开发规格_V1.1.md
├── lessons/
│   └── lesson_farm_01.json
├── contracts/
│   └── openapi.yaml
├── backend/
│   ├── app/{main.py,models.py,lesson_engine.py,exposure_engine.py,review.py}
│   ├── app/{game_adapter.py,speech_provider.py,storage.py}
│   └── tests/
├── bedrock-pack/
│   ├── behavior_pack/manifest.json
│   └── behavior_pack/scripts/main.js
├── voice-client/
│   └── ...
└── scripts/
    └── run_mock_demo.ps1
```

## 10.2 分阶段工单（必须按顺序交付）

**Milestone 0：离线课程引擎（先做）**  
实现 Pydantic schema、状态机、提示阶梯、SQLite、单元测试。`MockGameAdapter` 接收模拟实体点击。可通过 HTTP 控制完成第一课。**DoD：T01–T10 的非游戏环境测试通过。**

**Milestone 1：离线教学演示**  
实现预生成音频占位/播放器、教学语音状态、可视化简易测试页面或命令行演示。游戏尚未接入时仍可端到端完成 `cow/pig`。**DoD：不依赖 Minecraft 能演示第一课主要流程。**

**Milestone 2：Bedrock 游戏事件**  
创建可导入的简单行为包；检测对 cow/pig 的交互、位置或选中，调用 `GameAdapter`。先完成本地事件日志；联通 BDS 的 HTTP 前必须通过兼容性门槛测试。**DoD：实际 Windows/BDS 组合完成事件回传。**

**Milestone 3：游戏任务反馈**  
由 FastAPI 动作下发触发消息/高亮/开门，确保幂等。**DoD：孩子点击正确动物，仅触发一次场景变化。**

**Milestone 4：语音交互**  
加入 `MockSpeechProvider`→真实语音服务适配、按键说话、重听/跳过/录音状态。**DoD：固定词跟读、自愿口语、断网回退。**

**Milestone 5：复习与家长报告**  
实现跨课次简单复习规则、词汇理解日志和家长报告。**DoD：能区分 H0/H3、有跨天复习待办，报告不夸大掌握。**

每一个 milestone 都必须能独立运行演示；禁止在 Milestone 0 阶段接入大量 AI SDK 或开发整个 Minecraft 世界。

## 10.3 Codex 必须遵守的工程要求

- 使用 TypeScript/JavaScript + Python 3.12；FastAPI、Pydantic 2、pytest；版本以 lockfile 和当前官方兼容性为准。
- 所有外部服务定义接口和 mock；默认 `MOCK_MODE=true`，无需 Azure/OpenAI 密钥能跑单元/集成测试。
- 课程目标/脚本以数据驱动；AI 不得改写课程定义或直接执行原始 Minecraft 命令。
- 重要变更必须先列出拟修改文件和验收测试，再写代码。
- 使用环境变量存储外部 API 密钥；不得写入 Git。
- 每完成 milestone 输出：启动命令、测试结果、已实现/未实现、已验证/未验证的外部 API、下一步阻塞。

## 10.4 可直接复制给 Codex 的首轮任务

> 请将 `Minecraft_AI_英语启蒙教学与开发规格_V1.1.md` 作为产品与教学基线，遵守 `AGENTS.md`，读取 `lesson_farm_01.json` 和 `openapi.yaml`。**只实现 Milestone 0**：Python 3.12 + FastAPI + Pydantic v2 + SQLite + pytest；实现离线课程引擎、状态机、提示阶梯、去重事件、游戏与词汇掌握分离、进度查询，以及 MockGameAdapter/MockSpeechProvider。所有接口必须可离线测试。先提供文件树与实现计划，再分文件实现；不要调用未验证的 Minecraft 接口，不要接入真实云端 AI 服务。完成后运行测试，给出 Windows PowerShell 启动/请求示例，并说明未完成项。

---

# 11. 官方文档与需核实的依赖

1. Minecraft Bedrock Creator 文档： https://learn.microsoft.com/en-us/minecraft/creator/
2. Bedrock 事件开发： https://learn.microsoft.com/en-us/minecraft/creator/documents/scripting/events
3. `WorldAfterEvents`： https://learn.microsoft.com/en-us/minecraft/creator/scriptapi/minecraft/server/worldafterevents
4. NPC 创建及对话： https://learn.microsoft.com/en-us/minecraft/creator/documents/createnpcs
5. `@minecraft/server-net`（**BDS only / pre-release**）： https://learn.microsoft.com/en-us/minecraft/creator/scriptapi/minecraft/server-net/minecraft-server-net
6. Bedrock Dedicated Server： https://www.minecraft.net/en-us/download/server/bedrock
7. Azure Pronunciation Assessment： https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-pronunciation-assessment
8. OpenAI Realtime 文档： https://developers.openai.com/api/docs/guides/realtime

**资料核对日期：2026-11-24。** 技术选型基于公开官方文档，运行时兼容性、地区可用性和儿童语音准确率必须按目标环境实测。本文的课程比例、提示门槛和晋级规则是可调整的产品设计建议，不是经过标准化验证的教学结论。
