from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class MovieStatus(str, Enum):
    RELEASED = "Released"
    POST_PRODUCTION = "Post Production"
    IN_PRODUCTION = "In Production"


class CountryResponse(BaseModel):
    id: int
    code: str
    name: Optional[str]

    class Config:
        orm_mode = True


class GenreResponse(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class ActorResponse(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class LanguageResponse(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class MovieListItem(BaseModel):
    id: int
    name: str
    date: date
    score: float
    overview: str

    class Config:
        orm_mode = True


class MovieListResponse(BaseModel):
    movies: List[MovieListItem]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int


class MovieCreate(BaseModel):
    name: str = Field(..., max_length=255)
    date: date
    score: float = Field(..., ge=0, le=100)
    overview: str
    status: MovieStatus
    budget: float = Field(..., ge=0)
    revenue: float = Field(..., ge=0)
    country: str = Field(..., min_length=3, max_length=3)
    genres: List[str]
    actors: List[str]
    languages: List[str]

    @field_validator("date")
    def date_not_in_future(cls, v: date) -> date:
        max_date = date.today().replace(year=date.today().year + 1)
        if v > max_date:
            raise ValueError("Date must not be more than one year in the future")
        return v


class MovieResponse(BaseModel):
    id: int
    name: str
    date: date
    score: float
    overview: str
    status: str
    budget: float
    revenue: float
    country: CountryResponse
    genres: List[GenreResponse]
    actors: List[ActorResponse]
    languages: List[LanguageResponse]

    class Config:
        orm_mode = True


MovieDetailSchema = MovieResponse


class MovieUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    date: Optional[date] = None
    score: Optional[float] = Field(None, ge=0, le=100)
    overview: Optional[str] = None
    status: Optional[MovieStatus] = None
    budget: Optional[float] = Field(None, ge=0)
    revenue: Optional[float] = Field(None, ge=0)
    country: Optional[str] = Field(None, min_length=3, max_length=3)
    genres: Optional[List[str]] = None
    actors: Optional[List[str]] = None
    languages: Optional[List[str]] = None

    @field_validator("date")
    def date_not_in_future(cls, v: Optional[date]) -> Optional[date]:
        if v is not None:
            max_date = date.today().replace(year=date.today().year + 1)
            if v > max_date:
                raise ValueError("Date must not be more than one year in the future")
        return v


class MovieUpdateResponse(BaseModel):
    detail: str
