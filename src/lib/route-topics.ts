/**
/**
 * 优质网络线路专题元数据配置（面向 SEO 与专题聚合）。
 * 覆盖国内主流出海优质线路：CN2 GIA、联通 9929、移动 CMIN2、联通 4837。
 */

export interface RouteTopic {
  slug: string;
  name: string;
  lineKey: string;
  badge: string;
  carrier: "电信" | "联通" | "移动" | "三网";
  title: string;
  seoDescription: string;
  summary: string;
  highlights: string[];
  recommendFor: string;
  faqList: { question: string; answer: string }[];
}

export const ROUTE_TOPICS: Record<string, RouteTopic> = {
  "cn2-gia": {
    slug: "cn2-gia",
    name: "电信 CN2 GIA 专线",
    lineKey: "cn2_gia",
    badge: "电信顶级精品网",
    carrier: "电信",
    title: "CN2 GIA VPS 推荐与实时库存监测 - 电信顶级精品专线 | GoVPS",
    seoDescription:
      "2026 最新 CN2 GIA VPS 商家推荐与库存监控。实时追踪搬瓦工、DMIT、ZgoCloud 等主流主机商 CN2 GIA 套餐补货与降价，双程 CN2 GIA 晚高峰零丢包、低延迟，跨国业务首选。",
    summary:
      "CN2 GIA（China Telecom Next Carrying Network - Global Internet Access，AS4809）是中国电信最高优先级等级的跨境出网专线。去程与回程均直接调度至 CN2 骨干网核心路由（59.43.*.*），享有最高的 QoS 带宽保障，彻底告别晚高峰国际出口拥堵。",
    highlights: [
      "晚高峰零拥堵：拥有最高 QoS 传输优先级，即便国际海缆满载依然稳如泰山",
      "超低时延：美西洛杉矶至中国沿海延迟低至 120ms~150ms，日本/香港低至 30ms~60ms",
      "三网回程优化：多数高端机房采用三网回程强制走 CN2 GIA，联通和移动用户同样收益显著",
    ],
    recommendFor: "中国电信宽带用户、外贸建站、高频交易、远程桌面及对全天候稳定性有极致要求的业务。",
    faqList: [
      {
        question: "什么是 CN2 GIA？与普通 163 骨干网（GT/AS4134）有什么本质区别？",
        answer:
          "普通 163 骨干网（AS4134）节点以 202.97 开头，承载国内大部分廉价民用流量，晚高峰国际出口拥堵严重（丢包常达 15%~30%）。而 CN2 GIA（AS4809）节点全程经过 59.43 专网，容量轻载且具备最高优先级调度策略，晚高峰丢包接近 0%。",
      },
      {
        question: "如何确认一台 VPS 真正接入了 CN2 GIA？",
        answer:
          "可使用 NextTrace 或 BestTrace 进行去程与回程 MTR 路由跟踪。如果上海/广州/北京出口以及海外入境节点均出现 59.43.*.* 路由跳数，即证明真正走在 CN2 GIA 高速专线上。",
      },
      {
        question: "市面上有哪些口碑顶级的 CN2 GIA 服务商？",
        answer:
          "搬瓦工（BandwagonHost）DC6 / DC9 机房、DMIT Pro 系列（PVM.LAX.Pro）、ZgoCloud Los Angeles Optimised 系列均为业界公认一线标杆。GoVPS 实时监测以上各商家全系列实时库存与特惠变动。",
      },
    ],
  },
  "9929": {
    slug: "9929",
    name: "联通 AS9929 优质 A 网",
    lineKey: "9929",
    badge: "联通高端 A 网",
    carrier: "联通",
    title: "联通 9929 VPS 推荐与实时库存 - 联通高端 A 网精品专线 | GoVPS",
    seoDescription:
      "精选优质联通 AS9929 (CU2 / CU Premium) VPS 套餐推荐与库存监控。晚高峰超低丢包、大带宽性价比高，联通与电信三网访问极佳，实时追踪在售库存与特惠降价。",
    summary:
      "中国联通 AS9929（前身为中国网通 CNCnet 骨干网，业内常称 CU2 / CU Premium）是联通体系内的政企级高端专用网络。虽然不如 CN2 名气响亮，但其负载率极低，晚高峰抗拥堵性能完全媲美电信 CN2 GIA，且在大带宽与月付性价比上优势突出。",
    highlights: [
      "负载极轻：政企大客户专属专网，普通民用流量不接入，常年保持超低负载",
      "三网体验均衡：对北方联通及沿海电信网络均有极佳的互联互通延迟表现",
      "性价比更高：相比 CN2 GIA 动辄昂贵的价格，9929 通常提供更大的带宽冗余与更亲民的价格",
    ],
    recommendFor: "中国联通全部用户、北方宽带用户、追求稳定且需要 200M~1Gbps 大带宽出海的极客与团队。",
    faqList: [
      {
        question: "联通 9929 和联通 4837 有什么区别？",
        answer:
          "AS4837 是联通的普通民用骨干网（169 网），带宽便宜充沛，但在极端晚高峰大流量下会有抖动；而 AS9929 是联通的高端政企网络（A 网），专属独立核心，全天候不限速零拥堵，稳定性对标电信 CN2 GIA。",
      },
      {
        question: "哪些商家提供优质的 9929 VPS？",
        answer:
          "ZgoCloud、V.PS、DMIT、VMiss 等知名商家均有基于 9929 线路的优质 VPS 产品线，GoVPS 会实时追踪各套餐库存状态与降价通知。",
      },
    ],
  },
  "cmin2": {
    slug: "cmin2",
    name: "移动 CMIN2 精品网络",
    lineKey: "cmin2",
    badge: "移动专线对标 GIA",
    carrier: "移动",
    title: "移动 CMIN2 VPS 推荐与实时库存 - 移动专属出海高端专线 | GoVPS",
    seoDescription:
      "最新移动 CMIN2 (AS58807) VPS 推荐与补货监控。中国移动最高等级国际出口专线，移动宽带晚高峰直连不卡顿，对标电信 GIA 与联通 9929，低延迟高带宽在售机型汇总。",
    summary:
      "CMIN2（AS58807）是中国移动最新打造的国际高端精品网络，是移动用户对标电信 CN2 GIA 和联通 AS9929 的顶级方案。此前移动用户出海通常只能走 CMI（AS9808）普通骨干网，在晚高峰偶发拥堵；而 CMIN2 具备独立专属通道与 QoS 保障，彻底解决了移动宽带用户的痛点。",
    highlights: [
      "移动用户首选：中国移动宽带直连出海延迟最低、丢包率最低的终极选择",
      "高带宽冗余：支持 500Mbps 至 1Gbps 超大峰值带宽，兼顾速度与稳定性",
      "新一代架构：新建核心专网，目前网络容量冗余充足，晚高峰极度丝滑",
    ],
    recommendFor: "中国移动宽带用户、移动 5G 热点用户以及需要三网互补专线的跨国站点与应用。",
    faqList: [
      {
        question: "移动 CMIN2 和普通 CMI（AS9808）有什么区别？",
        answer:
          "普通 CMI（AS9808）是移动常规出口，遇流量高峰会偶发限速与跳 ping；CMIN2（AS58807）是移动单独划分的高端专网，拥有专享海缆带宽，享有最高优先级保障。",
      },
      {
        question: "电信和联通用户连 CMIN2 体验好吗？",
        answer:
          "许多高端 VPS 服务商配置了三网优质回程，电信走 GIA、联通走 9929、移动走 CMIN2，这被称为「三网顶级专线」。单 CMIN2 机房对移动最爽，其他宽带视各省互联 peer 情况而定。",
      },
    ],
  },
  "4837": {
    slug: "4837",
    name: "联通 AS4837 性价比之王",
    lineKey: "4837",
    badge: "大带宽性价比之王",
    carrier: "联通",
    title: "联通 4837 VPS 推荐与大带宽特惠 - 廉价高速出海方案 | GoVPS",
    seoDescription:
      "精选联通 AS4837 (CU1 / 169) VPS 主机推荐。超低价格享受 1Gbps~2.5Gbps 超大带宽，大流量下载与个人建站首选，实时监测年付神机与骨折降价。",
    summary:
      "中国联通 AS4837（联通 169 骨干网）是目前跨境 VPS 市场中带宽成本最低、性价比最高的网络方案。由于联通国际出口海缆带宽充沛，4837 往往能以极低价格（如 $10~$30/年）提供高达 1Gbps~2.5Gbps 的超大端口，是预算有限或大流量下载场景的绝对神机。",
    highlights: [
      "价格极低：年付十几美元即可拿下，是 CN2 GIA 价格的三分之一甚至更低",
      "超大带宽：普遍标配 1Gbps 到 2.5Gbps 物理端口，测速跑满千兆毫无压力",
      "日常体验优异：非极端晚高峰时期表现优异，日常下载与流媒体观看首选",
    ],
    recommendFor: "学生与个人极客、大文件同步与备份、大流量多媒体传输及追求极限性价比的用户。",
    faqList: [
      {
        question: "4837 晚高峰会卡吗？",
        answer:
          "4837 毕竟属于民用普通骨干网，在晚高峰（20:00~23:00）国际出口整体高负荷时，丢包率可能会有小幅上升（约 2%~8%），但其千兆大带宽即使降速也远高于普通限速小水管。",
      },
      {
        question: "有哪些超高性价比的 4837 代表产品？",
        answer:
          "V.PS 的 Mini/Starter 系列、VMiss 洛杉矶 Basic、DediOne 等均常年提供优质 4837 套餐，GoVPS 实时汇总低价在售现货。",
      },
    ],
  },
};
