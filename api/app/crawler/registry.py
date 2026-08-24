from .bandwagon import BandwagonCrawler
from .base import MerchantCrawler
from .dedione import DediOneCrawler
from .dmit import DmitCrawler
from .sixsixyun import SixSixYunCrawler
from .vmiss import VmissCrawler
from .vps import VPSCrawler
from .zgocloud import ZgoCloudCrawler

CRAWLERS: list[MerchantCrawler] = [
    DmitCrawler(),
    BandwagonCrawler(),
    VPSCrawler(),
    ZgoCloudCrawler(),
    DediOneCrawler(),
    VmissCrawler(),
    SixSixYunCrawler(),
]
