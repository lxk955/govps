/**
 * 页面访问上报（PV/UV 统计）。
 *
 * 不走 lib/api/client 的 apiFetch：埋点是 fire-and-forget，不应携带凭证、
 * 不应参与统一的错误/401 处理，失败也必须静默——统计缺失可以接受，
 * 影响页面功能则不行。
 */

const ENDPOINT = "/api/track/pageview";
const SESSION_KEY = "govps_sid";

/** 会话标识：sessionStorage 内生成，同一标签页生命周期内保持稳定。
 *  用于统计独立访客（UV）与跳出率。不用 IP 区分访客——请求经服务端 rewrite
 *  转发后后端看到的可能只是前端出口 IP，同一 IP 会覆盖大量真实访客。 */
function getSessionId(): string {
  try {
    let sid = sessionStorage.getItem(SESSION_KEY);
    if (!sid) {
      sid =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      sessionStorage.setItem(SESSION_KEY, sid);
    }
    return sid;
  } catch {
    // 隐私模式下 sessionStorage 可能抛错：退化为无会话标识，PV 仍可统计
    return "";
  }
}

export function trackPageView(path: string): void {
  try {
    const sessionId = getSessionId();
    const body = JSON.stringify({
      path,
      referrer: document.referrer || null,
      session_id: sessionId || null,
    });
    // keepalive：页面正在卸载（用户关闭/跳转外链）时请求仍有机会完成
    void fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    }).catch(() => {
      /* 静默：统计失败不影响使用 */
    });
  } catch {
    /* 静默 */
  }
}
