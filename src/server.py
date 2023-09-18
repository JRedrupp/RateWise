from fastapi import FastAPI
from src.const import AVAILABLE_CURRENCIES
from src.providers.ecb_daily import ECB_Daily_Feed

from pydantic import BaseModel
from enum import StrEnum
from typing import Union, Optional
import datetime


class CurrencyStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"


class CurrencyResponse(BaseModel):
    status: CurrencyStatus
    message: dict


class AvailableCurrency(BaseModel):
    code: str
    name: str


class ErrorMessage(BaseModel):
    code: str
    message: str


class AvailableCurrenciesResponse(CurrencyResponse):
    message: Union[list[AvailableCurrency], ErrorMessage]

    @classmethod
    def get_all_currencies(cls):
        return cls(
            status=CurrencyStatus.SUCCESS,
            message=[
                AvailableCurrency(code=code, name=currency["name"])
                for code, currency in AVAILABLE_CURRENCIES.items()
            ],
        )

    @classmethod
    def get_currency(cls, code: str):
        code = code.upper()
        if code not in AVAILABLE_CURRENCIES:
            return cls(
                status=CurrencyStatus.ERROR,
                message=ErrorMessage(
                    code="invalid_currency",
                    message="Invalid currency",
                ),
            )
        return cls(
            status=CurrencyStatus.SUCCESS,
            message=[
                AvailableCurrency(code=code, name=AVAILABLE_CURRENCIES[code]["name"])
            ],
        )


class ConvertResponse(CurrencyResponse):
    amount: Optional[float] = None
    base_currency: Optional[AvailableCurrency] = None
    target_currency: Optional[AvailableCurrency] = None
    converted_amount: Optional[float] = None
    rate: Optional[float] = None
    updated_datetime: Optional[datetime.datetime] = None
    message: Union[ErrorMessage, None] = None

    @classmethod
    async def get_conversion(cls, from_currency: str, to_currency: str, amount: float):
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        # Check if currencies are available
        if from_currency not in AVAILABLE_CURRENCIES:
            return cls(
                status=CurrencyStatus.ERROR,
                message=ErrorMessage(
                    code="invalid_currency", message=f"Invalid currency {from_currency}"
                ),
            )
        if to_currency not in AVAILABLE_CURRENCIES:
            return cls(
                status=CurrencyStatus.ERROR,
                message=ErrorMessage(
                    code="invalid_currency", message=f"Invalid currency {to_currency}"
                ),
            )

        # Get currency rates
        from_currency_rate = await ECB_Daily_Feed.get_currency_rate(from_currency)
        to_currency_rate = await ECB_Daily_Feed.get_currency_rate(to_currency)

        # Calculate conversion
        rate = to_currency_rate / from_currency_rate
        converted_amount = amount * (rate)

        return cls(
            status=CurrencyStatus.SUCCESS,
            amount=amount,
            base_currency=AvailableCurrency(
                code=from_currency, name=AVAILABLE_CURRENCIES[from_currency]["name"]
            ),
            target_currency=AvailableCurrency(
                code=to_currency, name=AVAILABLE_CURRENCIES[to_currency]["name"]
            ),
            converted_amount=converted_amount,
            rate=rate,
            updated_datetime=ECB_Daily_Feed.get_cache_date(),
        )


app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/available-currencies", response_model=AvailableCurrenciesResponse)
async def available_currencies():
    return AvailableCurrenciesResponse.get_all_currencies()


@app.get("/available-currencies/{code}", response_model=AvailableCurrenciesResponse)
async def available_currency(code: str):
    return AvailableCurrenciesResponse.get_currency(code)


@app.get(
    "/convert/{from_currency}/{to_currency}/{amount}", response_model=ConvertResponse
)
async def convert(from_currency: str, to_currency: str, amount: float):
    return await ConvertResponse.get_conversion(from_currency, to_currency, amount)
