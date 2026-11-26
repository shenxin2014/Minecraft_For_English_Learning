# 文档索引

本仓库面向 Windows 开发和运行。命令默认在**克隆后的仓库根目录**执行；示例 `D:\MinecraftBDS` 必须替换为实际测试服务器目录。

## 按使用目的阅读

1. **体验课堂**：[README](../README.md) → [M1 操作与验证](milestone-1.md)。
2. **接入真实游戏**：[M2 环境和事件诊断](milestone-2.md) → [M3 安装、建图与音画联调](milestone-3.md)。
3. **参与开发**：[开发指南](../CONTRIBUTING.md) → [架构](architecture.md) → [配置与接口](configuration.md) → [任务表](tasks.md)。
4. **处理问题**：[常见问题](troubleshooting.md)。

## 需求、设计与验证

| 文档 | 用途 |
| --- | --- |
| [原始规格 V1.1](Minecraft_AI_英语启蒙教学与开发规格_V1.1.md) | 保留原始需求，文末的旧阶段启动示例是历史材料 |
| [设计决定](decisions.md) | 缺失附件的补建、课程配置、事件归属和判定规则 |
| [M0 验证记录](milestone-0.md) | 离线课程引擎基线 |
| [M1 验证记录](milestone-1.md) | 浏览器农场与真实本地音频 |
| [M2 联调说明](milestone-2.md) | 事件接入候选与未完成的实机项 |
| [M3 联调说明](milestone-3.md) | 游戏闭环候选与未完成的实机项 |
| [OpenAPI](../contracts/openapi.yaml) | 与当前应用导出结果一致的接口契约 |
| [版本记录](../CHANGELOG.md) | 各阶段新增内容与当前状态 |

里程碑文件中的测试数量是该阶段的历史快照；当前总数以根 README 和实际测试输出为准。
历史文件中“本次环境”描述开发时检查的设备，不代表克隆者的设备状态。
M2/M3 文档中的版本是**候选组合**，没有隐含“已通过 Minecraft 加载验证”的承诺。
