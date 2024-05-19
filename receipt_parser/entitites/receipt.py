from typing import Optional
from pydantic import BaseModel, Field


class Receipt(BaseModel):
    receipt_number: Optional[str] = Field(None, description="Rechnungsnummer bzw. Identifikationsnummer")
    date: Optional[str] = Field(None, description="Datum der Rechnung")
    total_gross_amount: Optional[float] = Field(None, description="Summe der Rechnung mit MwSt.")
    total_net_amount: Optional[float] = Field(None, description="Summe der Rechnung ohne MwSt.")
    vat_amount: Optional[float] = Field(None, description="MwSt. Betrag")
    company_name: Optional[str] = Field(None, description="Name des ausstellenden Unternehmens")