import os
from datetime import datetime, timedelta
import httpx
import xmltodict
import json
from typing import Callable, Optional
from loguru import logger


class ECB_Daily_Feed:
    ECB_FEED = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
    CACHE_FILE = "data/ecb_daily.json"
    BASE_CURRENCY = "EUR"
    LAST_ECB_CALL_TIME = None
    CURRENT_CACHE_DATE = None

    cache_loader: Callable = json.load
    cache_dumper: Callable = json.dumps

    @classmethod
    def get_cache_date(cls, cache: Optional[dict] = None):
        """Get cache date from cache file."""
        if cache is not None:
            cls.CURRENT_CACHE_DATE = datetime.strptime(
                cache["gesmes:Envelope"]["Cube"]["Cube"]["@time"], "%Y-%m-%d"
            )
        return cls.CURRENT_CACHE_DATE

    @classmethod
    def cache_requires_update(cls):
        """Check if cache requires update."""

        if not os.path.exists(cls.CACHE_FILE):
            return True

        with open(cls.CACHE_FILE, "r") as cache:
            cache.seek(0, os.SEEK_END)
            if cache.tell() == 0:  # Empty file
                return True
            cache.seek(0)
            if (
                cls.LAST_ECB_CALL_TIME is not None
                and datetime.now() - cls.LAST_ECB_CALL_TIME < timedelta(hours=1)
            ):
                return False
            cache_date = cls.get_cache_date(cls.cache_loader(cache))
        if cache_date is None:
            return True
        return datetime.now() - cache_date > timedelta(days=1)

    @classmethod
    async def get_ecb_data(cls):
        """Check if ECB feed is available."""

        if cls.cache_requires_update():
            async with httpx.AsyncClient() as client:
                response = await client.get(cls.ECB_FEED)
                logger.info(f"ECB feed status code: {response.status_code}")
                response.raise_for_status()
                responseXml = xmltodict.parse(response.text)

                with open(cls.CACHE_FILE, "w") as cache:
                    cache.write(cls.cache_dumper(responseXml))
                    cls.LAST_ECB_CALL_TIME = datetime.now()

        with open(cls.CACHE_FILE, "r") as cache:
            return cls.cache_loader(cache)

    @classmethod
    async def get_currency_rate(cls, currency_code: str) -> float:
        """Get currency rate from ECB feed."""
        ecb_data = await cls.get_ecb_data()
        if currency_code == cls.BASE_CURRENCY:
            return 1.0
        for currency in ecb_data["gesmes:Envelope"]["Cube"]["Cube"]["Cube"]:
            if currency["@currency"] == currency_code:
                return float(currency["@rate"])
        raise ValueError(f"Currency {currency_code} not found in ECB feed.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(ECB_Daily_Feed.get_ecb_data())
