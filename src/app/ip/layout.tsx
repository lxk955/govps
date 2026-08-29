import type { Metadata } from "next";

import { IpNav } from "@/components/ip/ip-nav";
import "./ipcx.css";

export const metadata: Metadata = {
  title: "IP 检测",
  description:
    "IP 归属、纯净度与风险检测，WebRTC 泄露、DNS 泄露与浏览器指纹检测工具集。",
  alternates: { canonical: "/ip" },
};

/**
 * IP 检测板块框架（1:1 复刻旧站 views/ip/IpLayout.vue）：
 * .ipcx 命名空间 + sticky 二级导航 + 1080px 版心 + 板块页脚。
 *
 * `-mx-4 -my-6` 用于抵消全站 main 的 px-4/py-6，让板块背景铺满视口宽度
 * （旧站 .ipcx 自带 background，独立成一套视觉）。
 *
 * 旧站板块内自带的主题切换按钮已移除：主题改由全站 next-themes 统一控制，
 * 见 ipcx.css 顶部说明。
 */
export default function IpLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="ipcx -mx-4 -my-6">
      <div className="navbar">
        <div className="navbar__inner">
          <IpNav />
        </div>
      </div>
      <div className="wrap">
        {children}
        <footer className="foot">
          GoVPS · IP 归属、网络类型、威胁与代理情报、纯净度评分 —— 数据仅供参考
        </footer>
      </div>
    </div>
  );
}
