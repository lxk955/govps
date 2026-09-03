import { ImageResponse } from "next/og";

export const alt = "GoVPS · VPS雷达 - VPS 实时库存与降价监控";
export const size = {
  width: 1200,
  height: 630,
};
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "56px 64px",
          background: "radial-gradient(circle at 80% 20%, #1e3a8a 0%, #0b132b 50%, #030712 100%)",
          color: "#ffffff",
          fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
          position: "relative",
          boxSizing: "border-box",
        }}
      >
        {/* 顶部 Brand Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            width: "100%",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            {/* 雷达图符 */}
            <div
              style={{
                width: "48px",
                height: "48px",
                borderRadius: "12px",
                background: "linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: "0 0 24px rgba(59, 130, 246, 0.5)",
              }}
            >
              <svg
                width="30"
                height="30"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#ffffff"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="12" cy="12" r="9" />
                <circle cx="12" cy="12" r="4" />
                <line x1="12" y1="3" x2="12" y2="6" />
                <line x1="12" y1="18" x2="12" y2="21" />
                <line x1="3" y1="12" x2="6" y2="12" />
                <line x1="18" y1="12" x2="21" y2="12" />
              </svg>
            </div>
            <span style={{ fontSize: "32px", fontWeight: "900", letterSpacing: "-0.5px" }}>
              GoVPS
            </span>
            <span
              style={{
                fontSize: "16px",
                fontWeight: "700",
                background: "rgba(59, 130, 246, 0.2)",
                color: "#60a5fa",
                border: "1px solid rgba(96, 165, 250, 0.4)",
                padding: "4px 12px",
                borderRadius: "8px",
              }}
            >
              VPS雷达
            </span>
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              background: "rgba(16, 185, 129, 0.15)",
              border: "1px solid rgba(16, 185, 129, 0.3)",
              color: "#34d399",
              padding: "6px 14px",
              borderRadius: "9999px",
              fontSize: "15px",
              fontWeight: "600",
            }}
          >
            <div
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                background: "#10b981",
              }}
            />
            24/7 实时监控中
          </div>
        </div>

        {/* 中间核心标语与特性 */}
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          <h1
            style={{
              fontSize: "54px",
              fontWeight: "900",
              lineHeight: 1.15,
              letterSpacing: "-1px",
              margin: 0,
              background: "linear-gradient(to right, #ffffff, #93c5fd)",
              backgroundClip: "text",
              color: "transparent",
            }}
          >
            VPS 实时库存、线路对比与降价监控
          </h1>

          <p
            style={{
              fontSize: "22px",
              color: "#94a3b8",
              margin: 0,
              lineHeight: 1.5,
            }}
          >
            搬瓦工 · DMIT · V.PS · ZgoCloud · DediOne · VMISS · 66云
          </p>

          <div style={{ display: "flex", gap: "12px", marginTop: "12px" }}>
            <div
              style={{
                background: "rgba(255, 255, 255, 0.08)",
                border: "1px solid rgba(255, 255, 255, 0.12)",
                padding: "8px 18px",
                borderRadius: "10px",
                fontSize: "16px",
                fontWeight: "600",
                color: "#e2e8f0",
              }}
            >
              ⚡ 补货即时通报
            </div>
            <div
              style={{
                background: "rgba(255, 255, 255, 0.08)",
                border: "1px solid rgba(255, 255, 255, 0.12)",
                padding: "8px 18px",
                borderRadius: "10px",
                fontSize: "16px",
                fontWeight: "600",
                color: "#e2e8f0",
              }}
            >
              🏷️ 史低价格雷达
            </div>
            <div
              style={{
                background: "rgba(255, 255, 255, 0.08)",
                border: "1px solid rgba(255, 255, 255, 0.12)",
                padding: "8px 18px",
                borderRadius: "10px",
                fontSize: "16px",
                fontWeight: "600",
                color: "#e2e8f0",
              }}
            >
              🌐 CN2 GIA / 9929 / CMIN2 优质专线
            </div>
          </div>
        </div>

        {/* 底部站点信息 */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderTop: "1px solid rgba(255, 255, 255, 0.1)",
            paddingTop: "24px",
          }}
        >
          <span style={{ fontSize: "20px", color: "#60a5fa", fontWeight: "700" }}>
            https://govps.xyz
          </span>
          <span style={{ fontSize: "16px", color: "#64748b" }}>
            400+ 款热门海外 VPS 套餐全天候追踪
          </span>
        </div>
      </div>
    ),
    {
      ...size,
    }
  );
}
