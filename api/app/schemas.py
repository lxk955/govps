from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr

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
