from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field

CYCLE_TO_YEAR = {
    "monthly": 12,
    "quarterly": 4,
    "semi-annually": 2,
    "annually": 1,
    "biennially": Decimal("0.5"),
    "triennially": Decimal(1) / 3,
}


def yearly_price(price: Decimal, cycle: str) -> Decimal:
    # 各爬虫产出的周期写法不一（搬瓦工 "semi-annually"，V.PS/DMIT "semi_annually"），
    # 统一归一化为连字符形式再查表，避免半年付被按原价 ×1 折算
    factor = CYCLE_TO_YEAR.get((cycle or "").replace("_", "-"), 1)
    return (price * factor).quantize(Decimal("0.01"))


class MerchantOut(BaseModel):
    slug: str
    name: str

    model_config = {"from_attributes": True}


class ProductOut(BaseModel):
    id: int
    name: str
    merchant: MerchantOut
    cpu_cores: int | None
    ram_gb: Decimal | None
    disk_gb: int | None
    bandwidth_gb: int | None
    port_mbps: int | None
    location: str | None
    line_tags: list
    price: Decimal
    prev_price: Decimal | None
    currency: str
    billing_cycle: str
    in_stock: bool
    updated_at: datetime

    model_config = {"from_attributes": True}

    @property
    def price_yearly(self) -> Decimal:
        return yearly_price(self.price, self.billing_cycle)

    @property
    def price_dropped(self) -> bool:
        return self.prev_price is not None and self.price < self.prev_price


class SnapshotOut(BaseModel):
    checked_at: datetime
    price: Decimal | None = None
    in_stock: bool | None = None


class ProductDetail(ProductOut):
    price_snapshots: list[SnapshotOut] = []
    stock_snapshots: list[SnapshotOut] = []


class ProductListOut(BaseModel):
    total: int
    items: list[dict]


class TokenOut(BaseModel):
    token: str


class WatchIn(BaseModel):
    notify_restock: bool = True
    notify_price_drop: bool = True
    min_drop_percent: Decimal = Decimal(0)


class WatchOut(BaseModel):
    id: int
    product: ProductOut
    notify_restock: bool
    notify_price_drop: bool
    min_drop_percent: Decimal
    created_at: datetime


class NodeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    country: str = Field(default="hk", max_length=10)
    group_name: str = Field(default="主力", max_length=50)
    tags: list[str] = Field(default_factory=list)
    os_type: str | None = Field(default="linux", max_length=30)
    cpu_cores: int | None = 1
    price: float | None = None
    currency: str = Field(default="USD", max_length=10)
    billing_cycle: str = Field(default="monthly", max_length=20)
    expires_at: datetime | None = None
    traffic_limit_gb: float | None = None
    is_public: bool = False


class NodeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    country: str | None = Field(default=None, max_length=10)
    group_name: str | None = Field(default=None, max_length=50)
    tags: list[str] | None = None
    os_type: str | None = Field(default=None, max_length=30)
    cpu_cores: int | None = None
    price: float | None = None
    currency: str | None = Field(default=None, max_length=10)
    billing_cycle: str | None = Field(default=None, max_length=20)
    expires_at: datetime | None = None
    traffic_limit_gb: float | None = None
    is_public: bool | None = None


class ShareUpdate(BaseModel):
    enabled: bool = True
    public_node_ids: list[int] | None = None


class PingMetric(BaseModel):
    name: str  # 电信 / 联通 / 移动
    latency_ms: float
    loss_rate: float = 0.0


class NodeReport(BaseModel):
    cpu_percent: float = 0.0
    cpu_cores: int | None = None
    ram_used_bytes: int = 0
    ram_total_bytes: int = 0
    swap_used_bytes: int = 0
    swap_total_bytes: int = 0
    disk_used_bytes: int = 0
    disk_total_bytes: int = 0
    load_1: float = 0.0
    load_5: float = 0.0
    load_15: float = 0.0
    net_rx_rate: float = 0.0
    net_tx_rate: float = 0.0
    net_rx_total: int = 0
    net_tx_total: int = 0
    uptime_seconds: int = 0
    os_type: str | None = None
    os_version: str | None = None
    kernel_version: str | None = None
    arch: str | None = None
    agent_version: str | None = None
    auto_update: bool = True
    ping_stats: list[PingMetric] = Field(default_factory=list)

