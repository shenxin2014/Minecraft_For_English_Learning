import { secrets, variables } from "@minecraft/server-admin";
import { HttpHeader, HttpRequest, HttpRequestMethod, http } from "@minecraft/server-net";

/** 使用 BDS 模块专属配置；令牌始终以 SecretString 交给网络模块。 */
export class BdsTransport {
  /** 本阶段限定同机 loopback，避免无意把共享令牌发送到外部地址。 */
  constructor() {
    this.baseUrl = variables.get("farm_api_url");
    this.token = secrets.get("farm_bds_token");
    if (typeof this.baseUrl !== "string" || !/^http:\/\/127\.0\.0\.1:\d{1,5}$/.test(this.baseUrl)) {
      throw new Error("LOOPBACK_API_URL_REQUIRED");
    }
    if (!this.token) throw new Error("BDS_SECRET_MISSING");
  }

  /** 发送有超时的 JSON 请求；异常只携带状态码，不包含秘密或响应正文。 */
  async request(path, body = null) {
    const request = new HttpRequest(`${this.baseUrl}${path}`);
    request.method = body === null ? HttpRequestMethod.Get : HttpRequestMethod.Post;
    request.timeout = 5;
    request.headers = [
      new HttpHeader("X-BDS-Token", this.token),
      new HttpHeader("Content-Type", "application/json"),
    ];
    if (body !== null) request.body = JSON.stringify(body);
    const response = await http.request(request);
    if (response.status < 200 || response.status >= 300) {
      const error = Object.assign(new Error("BDS_HTTP_FAILED"), { status: response.status });
      throw error;
    }
    return JSON.parse(response.body);
  }

  /** 获取服务端权威任务与匿名玩家绑定。 */
  context(bridgeId) {
    return this.request(`/v1/bds/context/${bridgeId}`);
  }

  /** 单独验证网络通路；不会伪造实体事件。 */
  probe(bridgeId, profile) {
    return this.request("/v1/bds/probe", {
      bridge_id: bridgeId,
      pack_version: profile.startsWith("m3-") ? "0.4.0" : "0.3.0",
      runtime_profile: profile,
    });
  }

  /** 原样重发持久化事件，包括原始任务、时间、ID 和序号。 */
  send(envelope) {
    return this.request("/v1/bds/events", envelope);
  }
}
