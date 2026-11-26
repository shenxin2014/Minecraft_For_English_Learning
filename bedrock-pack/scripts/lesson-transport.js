import { BdsTransport } from "./transport.js";

/** M3 网络通道扩展；沿用 BDS 私密令牌及回环地址约束。 */
export class LessonTransport extends BdsTransport {
  /** 游戏控制与视觉回执使用独立的受限 M3 契约。 */
  send(envelope) {
    return this.request("/v1/bds/lesson/events", envelope);
  }

  /** 原子获取权威状态和当前允许执行的游戏动作。 */
  actions(bridgeId) {
    return this.request(`/v1/bds/lesson/actions/${bridgeId}`);
  }

  /** 执行成功才发送 ACK，失败重试沿用原 command_id。 */
  ack(bridgeId, command) {
    return this.request(`/v1/bds/lesson/ack/${command.command_id}`, {
      bridge_id: bridgeId,
      session_id: command.session_id,
      success: true,
    });
  }

  /** 心跳仅报告可见性，不代替视觉动作或媒体播放回执。 */
  presence(context, visible) {
    return this.request("/v1/bds/lesson/presence", {
      bridge_id: context.bridge_id,
      task_id: context.session.current_task.task_id,
      visual_id: context.session.active_visual_id,
      visible,
    });
  }

  /** 只上传本进程实际计时的样本，缺失计时不会填零。 */
  latency(bridgeId, commandId, elapsed) {
    return this.request("/v1/bds/lesson/latency", {
      bridge_id: bridgeId,
      command_id: commandId,
      elapsed_ms: elapsed,
    });
  }
}
