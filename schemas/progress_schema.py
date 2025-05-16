from pydantic import BaseModel, Field, validator
from typing import List, Union

# Use date for simplicity if time is not needed
from datetime import date


class ProgressEntry(BaseModel):
    # Assuming date is stored as string e.g., "YYYY-MM-DD" or integer timestamp
    # For simplicity, let's use date type and convert if needed during load/save
    # 'date' is the key in JSON
    day_date: Union[date, str] = Field(..., alias="date")
    score: float  # Or int, depending on what score represents

    @validator("day_date", pre=True)
    def parse_date_str(cls, v):
        if isinstance(v, str):
            try:
                return date.fromisoformat(v)
            except ValueError as e:
                raise ValueError(
                    f"Invalid date format: {v}. Expected YYYY-MM-DD."
                ) from e
        if isinstance(v, date):
            return v
        raise TypeError("Date must be a string in YYYY-MM-DD format or a date object.")

    class Config:
        populate_by_name = True  # Changed from allow_population_by_field_name


class ProgressData(BaseModel):
    history: List[ProgressEntry] = []
