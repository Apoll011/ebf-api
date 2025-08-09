from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import date, datetime
from . import crud
from .dependencies import get_db

class StudentBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    notes: Optional[str] = Field(None, min_length=2, max_length=500)
    age: int = Field(..., ge=0, le=18)
    gender: str
    parent_name: Optional[str] = Field(None, min_length=2, max_length=50)
    parent_phone: Optional[str] = None
    address: Optional[str] = None

    @validator('gender')
    def gender_must_be_valid(cls, v):
        if v.lower() not in ['male', 'female', 'other']:
            raise ValueError('gender must be male, female, or other')
        return v.lower()

class StudentCreate(StudentBase):
    @validator('name')
    def name_must_not_be_duplicate(cls, v):
        db = next(get_db())
        if crud.get_student_by_name(db, name=v):
            raise ValueError('Student with this name already exists')
        return v

class StudentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=50)
    age: Optional[int] = Field(None, ge=0, le=18)
    gender: Optional[str] = None
    address: Optional[str] = Field(None, max_length=200)
    parent_name: Optional[str] = Field(None, min_length=2, max_length=50)
    parent_phone: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=500)

    @validator('gender')
    def gender_must_be_valid(cls, v):
        if v is not None and v.lower() not in ['male', 'female', 'other']:
            raise ValueError('gender must be male, female, or other')
        return v.lower() if v is not None else v

class PointsBase(BaseModel):
    presence: bool = False
    book: bool = False
    versicle: bool = False
    participation: bool = False
    guest: bool = False
    game: bool = False

class PointsCreate(BaseModel):
    award_date: date = Field(default_factory=date.today)
    points: PointsBase

    @validator('award_date')
    def date_must_not_be_in_the_future(cls, v):
        if v > date.today():
            raise ValueError('Cannot award points for a future date')
        return v

class PointsResponse(PointsBase):
    id: int
    award_date: date
    total: int

    class Config:
        orm_mode = True

class PointAdjustment(BaseModel):
    amount: int
    reason: str
    date_adjust: date = Field(default_factory=date.today)


class StudentResponse(StudentBase):
    id: str
    group: str
    total_points: int
    created_at: datetime

    class Config:
        orm_mode = True

class StudentDetailResponse(StudentResponse):
    points_records: List[PointsResponse] = []
    
    class Config:
        orm_mode = True

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str
    role: str = "viewer"

class User(UserBase):
    id: int
    role: str

    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class ClassResponse(BaseModel):
    id: str
    name: str
    description: str
    min_age: int
    max_age: int
    student_count: int

class TeacherResponse(BaseModel):
    id: str
    name: str
    phone: str
    email: str
    specialization: str
    years_experience: int

