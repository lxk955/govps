import enum
from datetime import datetime, timezone

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
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

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    in_stock: Mapped[bool] = mapped_column(Boolean)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


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
