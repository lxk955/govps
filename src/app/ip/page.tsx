import { IpCheckPanel } from "@/components/ip/ip-check-panel";

export default function IpHomePage() {
  return (
    <>
      <header className="mb-4">
        <h1 className="text-xl font-bold tracking-tight lg:text-2xl">IP 检测</h1>
        <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
          查询 IP 归属、运营商、机房识别与纯净度评分；购买 VPS 前，先看看你与机房之间线路两端的「身份」。
        </p>
      </header>
      <IpCheckPanel />
    </>
  );
}
