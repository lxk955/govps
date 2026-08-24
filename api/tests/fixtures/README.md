# Crawler Fixtures

录制自真实商家站点的回放样本，供 `test_crawler_*.py` 禁网回放使用（AGENTS.md Crawler Testing）。

| 文件 | 来源 | 录制日期 |
|---|---|---|
| bandwagon/get-data.json | https://bwh81.net/order/get-data | 2026-08-23 |
| dedione/store-special.html | https://dedione.com/store/special-vps-plans | 2026-08-23 |
| dmit/plans.json | monitor.vpszk.com（DMIT 主源） | 2026-08-24 |
| dmit/vpsoso.html | vpsoso.com（DMIT 备源） | 2026-08-24 |
| sixsixyun/cart-gid6.html | 666clouds.com/cart.php?gid=6 | 2026-08-24 |
| sixsixyun/home.html | 666clouds.com 首页 | 2026-08-24 |
| zgocloud/special-offer.html | clients.zgovps.com 分组页 | 2026-08-24 |
| vmiss/stockvps-page.html | stockvps.org 首页内嵌监控数据（裁剪至 3 条计划，其中 1 条库存值改写为 0，见文件头注释） | 2026-08-24 |

约定：
- 常规测试**只允许**通过 httpx.MockTransport / 直接传入 HTML 字符串消费这些文件，禁止任何真实网络请求；
- 商家改版导致解析断言失败时，重新录制并在本表更新日期，同时在提交说明中注明差异；
- vmiss / vps 官网直连被源站盾拦截（录制 403），`test_crawler_fixtures.py` 中这两家的
  实时目录用例使用按真实模板构造的**合成**页面（文件内联定义并注明），第三方监控源
  （stockvps.org）等可达路径一律使用上表录制样本；
- 四类覆盖契约：normal（录制样本回放）/ changed（关键选择器或字段改名 → 解析 0 款不抛异常，
  或按阈值回退预置目录）/ incomplete（空数据、部分源失败）/ error（HTTP 5xx → 各 adapter
  契约逐一固化）。
