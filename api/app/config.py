from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "sqlite:///./data/govps.db"
    TASK_TOKEN: str = "change-me"
    RESEND_API_KEY: str = ""
    MAIL_FROM: str = "GoVPS · VPS雷达 <notify@govps.xyz>"
    PUBLIC_API_URL: str = "http://localhost:8000"
    CORS_ORIGINS: str = "http://localhost:5173"
    EVENT_DEDUP_MINUTES: int = 30
    DAILY_MAIL_CAP: int = 10
    SCAN_TIMEOUT: float = 20.0
    # P7 分级调度：全局兜底抓取间隔（分钟）；商家列 crawl_interval_minutes 优先，
    # 其次 adapter 的 default_interval_minutes，最后此全局值。env 可覆盖。
    # 2026-08-31 运营决策：全商家统一 5 分钟（与 cron 触发周期一致，即每轮全量）。
    CRAWL_INTERVAL_MINUTES: int = 5
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
    # 启动全量扫描开关：默认设为 True，避免服务启动时阻塞在 7 家商家外部爬取导致健康检查超时
    SKIP_STARTUP_SCAN: bool = True
    # 自动汇率抓取开关：启动时兜底拉取与扫描收尾的日更都会请求外部汇率源。
    # 测试环境置 True 以满足「常规测试禁网」，也避免污染汇率用例的 fixture；
    # 汇率本身的逻辑由 tests/test_rates.py 用隔离数据单独覆盖。
    SKIP_AUTO_RATES: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        # 基础来源 + 自动包含后端自身公网域名（便于同域调试与 /go 跳转）
        origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if self.PUBLIC_API_URL and self.PUBLIC_API_URL not in origins:
            origins.append(self.PUBLIC_API_URL)
        return origins


settings = Settings()
