from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "sqlite:///./vps_scout.db"
    TASK_TOKEN: str = "change-me"
    RESEND_API_KEY: str = ""
    MAIL_FROM: str = "VPS 雷达 <notify@govps.xyz>"
    PUBLIC_API_URL: str = "http://localhost:8000"
    CORS_ORIGINS: str = "http://localhost:5173"
    EVENT_DEDUP_MINUTES: int = 30
    DAILY_MAIL_CAP: int = 10
    SCAN_TIMEOUT: float = 20.0
    # P7 分级调度：全局兜底抓取间隔（分钟）；商家列 crawl_interval_minutes 优先，
    # 其次 adapter 的 default_interval_minutes，最后此全局值。env 可覆盖。
    CRAWL_INTERVAL_MINUTES: int = 15
    # P7 邮件异步 worker：进程内后台线程消费 pending NotifyLog
    NOTIFY_WORKER_ENABLED: bool = True
    NOTIFY_WORKER_INTERVAL_SECONDS: int = 10
    EMAIL_MAX_ATTEMPTS: int = 3
    # P5 汇率源（均为无密钥公开端点，base=USD 报价；若未来换 keyed 源，密钥只经环境变量）
    EXCHANGE_RATE_API_URL: str = "https://open.er-api.com/v6/latest/USD"
    EXCHANGE_RATE_FALLBACK_API_URL: str = "https://api.frankfurter.dev/v1/latest?base=USD"
    EXCHANGE_RATE_TIMEOUT: float = 10.0
    # 自动源相对现值允许的最大漂移（超出视为异常数据拒绝写入，需人工覆盖）
    EXCHANGE_RATE_MAX_DEVIATION: float = 0.5
    # 测试/本地可关：避免 import app.main 时阻塞在全量抓取
    SKIP_STARTUP_SCAN: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        # 基础来源 + 自动包含后端自身公网域名（便于同域调试与 /go 跳转）
        origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if self.PUBLIC_API_URL and self.PUBLIC_API_URL not in origins:
            origins.append(self.PUBLIC_API_URL)
        return origins


settings = Settings()
