import enum
from datetime import datetime, timezone

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_iso_utc(dt: datetime | None) -> str | None:
    """保证输出含 +00:00 明确时区后缀，避免 SQLite 存取的朴素时间被前端默认当作本地时间解析导致时差。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    website: Mapped[str] = mapped_column(String(255))
    # 返利链接模板，支持 {url}（购买页地址）和 {pid}（商家产品ID）占位符；为空则直链
    aff_url_template: Mapped[str | None] = mapped_column(String(500), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # 最近一次成功抓取时间（用于识别同步停滞；失败时保持旧值）
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 最近一次抓取错误信息（成功时清空）
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # P7：该商家的抓取间隔（分钟）。NULL 时回退 adapter 默认值（default_interval_minutes）；
    # 运营可直接改库覆盖，无需改代码。到期判断见 services/scan.run_scan。
    crawl_interval_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    products: Mapped[list["Product"]] = relationship(back_populates="merchant")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(100))  # 商家侧产品ID（如 WHMCS 的 pid）
    name: Mapped[str] = mapped_column(String(255), index=True)

    cpu_cores: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ram_gb: Mapped[float | None] = mapped_column(Numeric(6, 1), nullable=True)
    disk_gb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bandwidth_gb: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 月流量
    port_mbps: Mapped[int | None] = mapped_column(Integer, nullable=True)

    location: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    line_tags: Mapped[list] = mapped_column(JSON, default=list)  # ["CN2 GIA", "9929", ...]

    price: Mapped[float] = mapped_column(Numeric(10, 2))
    prev_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    billing_cycle: Mapped[str] = mapped_column(String(20), default="annually")
    price_options: Mapped[list] = mapped_column(JSON, default=list)  # [{"billing_cycle": "monthly", "price": 19.99, "currency": "USD", "purchase_url": "..."}, ...]

    purchase_url: Mapped[str] = mapped_column(String(500))
    # 悲观默认 False：任何未显式赋值的创建路径都不应显示有货
    in_stock: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    recommended: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    # 最近一次被成功抓取确认的时间（每次有效抓取无条件刷新，与 updated_at 的区别是
    # 后者只在字段值变化时更新，无法区分「没被扫到」和「状态没变」）
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── P1 物化列（refactor-plan §2 #1/#9：计算时机从每次请求迁移到扫描期）──
    # 均为可空增量列：旧代码不读即无害，回滚无需 DB 动作（refactor-plan §4）
    # 聚合键：spec_group_key 元组的规范化 JSON 序列化；同款不同周期/pid 聚合为一张卡片
    spec_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 全量可搜索文本（名称/商家/机房/线路/别名/规格），小写；关键词过滤下推 SQL 用
    search_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 线路标签纯文本（空格连接的小写标签）：线路筛选下推 SQL 用。
    # 不直接 LIKE JSON 文本——SQLite 方言默认 ensure_ascii 序列化会把中文转义成 \uXXXX
    line_tags_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 三项评分与推荐理由，扫描期按既有公式物化（公式零改动）；请求期不再逐条计算
    hot_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    deal_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    popularity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        # 商家侧产品天然唯一（upsert 幂等的库级保证）。
        # 注意：此前与下面的 Index 曾写成两个 __table_args__，Python 类体后者覆盖前者，
        # 导致 P1 起新建库静默丢失本约束——迁移 parity 测试（test_migrations）防复发
        UniqueConstraint("merchant_id", "external_id"),
        # /go 与聚合水合路径：WHERE merchant_id = ? AND spec_key = ?
        Index("ix_products_merchant_spec", "merchant_id", "spec_key"),
    )

    merchant: Mapped[Merchant] = relationship(back_populates="products")


class StockSnapshot(Base):
    __tablename__ = "stock_snapshots"
    __table_args__ = (Index("ix_stock_snapshots_product_checked", "product_id", "checked_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    in_stock: Mapped[bool] = mapped_column(Boolean)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"
    __table_args__ = (Index("ix_price_snapshots_product_checked", "product_id", "checked_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    api_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    view_mode: Mapped[str] = mapped_column(String(20), default="card")
    currency_mode: Mapped[str] = mapped_column(String(20), default="original")
    monitor_public_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    monitor_share_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    monitor_share_ip_mode: Mapped[str] = mapped_column(String(20), default="mask", server_default="mask")
    monitor_expire_notify_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    monitor_expire_stages: Mapped[list] = mapped_column(JSON, default=lambda: [15, 7, 3, 1])
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    nodes: Mapped[list["UserNode"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class SiteSetting(Base):
    """管理后台可改的站点配置（覆盖 .env 同名项）。"""

    __tablename__ = "site_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(500), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class EmailCode(Base):
    __tablename__ = "email_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    code: Mapped[str] = mapped_column(String(6))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Watchlist(Base):
    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("user_id", "product_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    notify_restock: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_price_drop: Mapped[bool] = mapped_column(Boolean, default=True)
    min_drop_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    product_ref: Mapped[Product] = relationship()


class ExchangeRate(Base):
    """当前汇率（P5）：units_per_usd = 兑 1 美元所需该币种单位数
    （如 CNY 7.2 表示 7.2 元/美元）。USD 金额 = 外币金额 ÷ units_per_usd。

    独立存储，永不回写产品价格；source 区分自动抓取与人工覆盖。
    USD 恒为 1.0，保证换算口径统一。"""
    __tablename__ = "exchange_rates"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    units_per_usd: Mapped[float] = mapped_column(Numeric(16, 8))
    source: Mapped[str] = mapped_column(String(20), default="auto")  # auto | manual
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ExchangeRateSnapshot(Base):
    """每日汇率快照（P5）：units_per_usd 同上；历史价格分析按「快照日期」取值，
    不得用当前汇率回算历史。unique(code,date) 保证每日一行，幂等覆盖。"""
    __tablename__ = "exchange_rate_snapshots"
    __table_args__ = (UniqueConstraint("code", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), index=True)
    date: Mapped[date] = mapped_column(Date)
    units_per_usd: Mapped[float] = mapped_column(Numeric(16, 8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EventType(str, enum.Enum):
    RESTOCK = "RESTOCK"
    PRICE_DROP = "PRICE_DROP"


class NotifyEvent(Base):
    __tablename__ = "notify_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    type: Mapped[str] = mapped_column(String(20), index=True)
    old_value: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    product: Mapped[Product] = relationship()


class NotifyLog(Base):
    __tablename__ = "notify_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("notify_events.id"))
    channel: Mapped[str] = mapped_column(String(20), default="email")  # email / sms 预留
    # P7 异步化：pending（待发送，可重试）/ sent / failed（重试耗尽）/ skipped
    status: Mapped[str] = mapped_column(String(20))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AffClick(Base):
    __tablename__ = "aff_clicks"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # 点击来源：site_click（列表页埋点）/ card / row / detail（/go 跳转入口）/
    # email_restock / email_drop（邮件内链接）；缺货被插页拦截时追加 _oos 后缀
    src: Mapped[str] = mapped_column(String(32), default="site")
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ua: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class PageView(Base):
    """页面访问记录（PV/UV 统计）。

    前端在路由变化时上报，用于回答「各页面真实访问量」这类问题（例如首页是否
    值得保留）。与 AffClick 的区别：后者记录购买跳转意向，本表记录浏览行为。

    route 是归一化后的路由（/vps/93-xxx → /vps/[slug]），按页面聚合时用它；
    path 保留原始路径用于排查。

    session_id 由前端 sessionStorage 生成，是统计独立访客（UV）与跳出率的依据。
    不依赖 IP 区分访客：请求经 Next.js rewrite 转发后，后端拿到的可能是前端服务
    的出口 IP（详见 services/client_ip 的说明），同一 IP 会覆盖大量真实访客。
    """

    __tablename__ = "page_views"
    __table_args__ = (
        # 按页面 + 时间范围统计 PV
        Index("ix_page_views_route_created", "route", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    route: Mapped[str] = mapped_column(String(120), index=True)
    path: Mapped[str] = mapped_column(String(255))
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id"), nullable=True, index=True
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    referrer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ua: Mapped[str | None] = mapped_column(String(255), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class RequestRateEvent(Base):
    """IP 限流滑动窗口事件（P7 #10）：旧实现为进程内 deque，多 worker / 重启即失效；
    迁移为 DB 计数后窗口跨进程连续。表体量由 services/rate_limit 的周期清理约束在
    「最近窗口 × 请求量」量级。判定逻辑见 hit_rate_limited。"""

    __tablename__ = "request_rate_events"
    __table_args__ = (
        # 窗口计数查询：WHERE ip = ? AND created_at >= ?
        Index("ix_request_rate_events_ip_created", "ip", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ip: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class DnsLeakHit(Base):
    """DNS 泄露检测命中记录。

    记录来自递归解析器（Resolver）对 *.dnstest.<domain> 的查询请求。
    """

    __tablename__ = "dns_leak_hits"
    __table_args__ = (
        Index("ix_dns_leak_hits_token_created", "token", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(64), index=True)
    resolver_ip: Mapped[str] = mapped_column(String(64), index=True)
    query_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class CrawlLog(Base):
    """爬虫执行历史流水记录。

    记录每次商家调度抓取的执行耗时、商品数、官方一手占比、实时在售数、抓取方式与结果状态。
    """

    __tablename__ = "crawl_logs"
    __table_args__ = (
        Index("ix_crawl_logs_slug_created", "merchant_slug", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchants.id"), nullable=True, index=True)
    merchant_name: Mapped[str] = mapped_column(String(100))
    merchant_slug: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)  # "success", "partial", "degraded", "failed"
    method: Mapped[str] = mapped_column(String(150))
    products_count: Mapped[int] = mapped_column(Integer, default=0)
    official_count: Mapped[int] = mapped_column(Integer, default=0)
    in_stock_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class UserNode(Base):
    """用户自建/托管的 VPS 探针节点。"""

    __tablename__ = "user_nodes"
    __table_args__ = (
        Index("ix_user_nodes_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    country: Mapped[str] = mapped_column(String(10), default="hk")  # hk, jp, us, sg, de, gb, etc.
    group_name: Mapped[str] = mapped_column(String(50), default="主力")
    tags: Mapped[list] = mapped_column(JSON, default=list)  # ["主力", "V4", "V6", "CN2 GIA"]
    os_type: Mapped[str] = mapped_column(String(30), default="debian")  # debian, ubuntu, centos, alpine, arch, windows
    os_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    arch: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cpu_cores: Mapped[int | None] = mapped_column(Integer, nullable=True, default=1)

    price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    billing_cycle: Mapped[str] = mapped_column(String(20), default="monthly")  # monthly, annually, quarterly, triennially
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expire_notify_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    expire_notify_stages: Mapped[list | None] = mapped_column(JSON, nullable=True, default=None)
    notified_expire_stages: Mapped[list] = mapped_column(JSON, default=list)
    expire_muted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    traffic_limit_gb: Mapped[float | None] = mapped_column(Float, nullable=True)
    traffic_direction: Mapped[str] = mapped_column(String(10), default="both", server_default="both")
    cycle_traffic_rx: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    cycle_traffic_tx: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    cycle_traffic_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reported_rx: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None)
    last_reported_tx: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None)
    public_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # 冗余缓存最新状态字段，避免首页高频轮询每次关联快照大表
    cached_status: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship(back_populates="nodes")
    snapshots: Mapped[list["NodeSnapshot"]] = relationship(
        back_populates="node", cascade="all, delete-orphan"
    )


class NodeSnapshot(Base):
    """节点时序指标快照（用于详情历史图表）。"""

    __tablename__ = "node_snapshots"
    __table_args__ = (
        Index("ix_node_snapshots_node_recorded", "node_id", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("user_nodes.id"), index=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    cpu_percent: Mapped[float] = mapped_column(Float, default=0.0)
    ram_used_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    ram_total_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    swap_used_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    swap_total_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    disk_used_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    disk_total_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    load_1: Mapped[float] = mapped_column(Float, default=0.0)
    load_5: Mapped[float] = mapped_column(Float, default=0.0)
    load_15: Mapped[float] = mapped_column(Float, default=0.0)
    net_rx_rate: Mapped[float] = mapped_column(Float, default=0.0)
    net_tx_rate: Mapped[float] = mapped_column(Float, default=0.0)
    net_rx_total: Mapped[int] = mapped_column(BigInteger, default=0)
    net_tx_total: Mapped[int] = mapped_column(BigInteger, default=0)
    uptime_seconds: Mapped[int] = mapped_column(BigInteger, default=0)
    ping_stats: Mapped[list] = mapped_column(JSON, default=list)

    node: Mapped["UserNode"] = relationship(back_populates="snapshots")

