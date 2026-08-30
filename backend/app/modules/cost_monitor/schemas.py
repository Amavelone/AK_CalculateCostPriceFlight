from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LegInput(BaseModel):
    id: str
    departure: str = ""
    arrival: str = ""
    aircraft: str = "738"
    passengers: int = Field(default=0, ge=0, le=1000)

    @field_validator("departure", "arrival", "aircraft")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class CalculationSettings(BaseModel):
    scenario: str = "ГБ 2026"
    fuel_source: Literal["ЦРТ", "АК"] = "ЦРТ"
    techstop_leg_id: str | None = None
    # Соответствует исходному значению AA2 текущей книги: фиксированная стоимость
    # питания присутствует всегда, а этот флаг включает доплату за пассажиров.
    catering: bool = False
    show_details: bool = True


class CalculationRequest(BaseModel):
    legs: list[LegInput] = Field(default_factory=list)
    settings: CalculationSettings = Field(default_factory=CalculationSettings)


class SourceConfigUpdate(BaseModel):
    directory: str = Field(min_length=1, max_length=600)
    mask: str = Field(min_length=1, max_length=120)


class ManualTariffInput(BaseModel):
    airport: str = Field(min_length=3, max_length=3)
    service: str = Field(min_length=1, max_length=100)
    rate: float = Field(ge=0)
    unit: str = Field(default="РУБ-ЕД", max_length=40)
    aircraft: str = Field(default="", max_length=20)
    note: str = Field(default="", max_length=500)

    @field_validator("airport", "aircraft")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("service", "unit", "note")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip()


class DraftPayload(BaseModel):
    calculation: CalculationRequest
