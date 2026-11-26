# 第三方与素材说明

## 依赖

Python 和 Node 开发依赖分别记录在 `requirements.lock`、`pyproject.toml`、`package.json` 与 `package-lock.json`。
第三方依赖按其各自许可证使用；本仓库不复制 Python/Node 安装目录。
Minecraft Script API 类型包用于开发检查，游戏运行时由对应 Bedrock/BDS 提供模块。

## 本地素材

- `frontend/assets/*.svg`：本项目开发过程中编写的 SVG 插画与场景。
- `frontend/assets/audio/*.wav`：通过 Windows SAPI 的 Microsoft Zira Desktop 英语声线本地合成，不是真人或儿童录音。
- 音频文本、声线和参数见 `frontend/assets/audio/manifest.json`；生成脚本见 `scripts/generate_audio.ps1`。
- 重新生成音频需要安装对应 Windows 声线；正常运行无需重新生成。

## Minecraft

仓库不包含 Minecraft 客户端、BDS 可执行文件或从游戏提取的材质与模型。
行为包使用的原版实体、粒子和声音由用户安装的游戏提供。
本项目为独立教学原型，不是 Mojang 或 Microsoft 的官方产品。

## 仓库许可状态

当前仓库没有声明单独的开源许可证。本说明记录来源，不替代第三方条款，也不为项目自动授予额外许可。
