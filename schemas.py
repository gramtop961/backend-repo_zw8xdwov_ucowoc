"""
Database Schemas for Daily Life Optimizer

Each Pydantic model maps to a MongoDB collection named after the class in lowercase.
Use these for validation on create endpoints.
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import date, time


class Task(BaseModel):
    title: str = Field(..., description="Short task title")
    details: Optional[str] = Field(None, description="Optional notes")
    priority: int = Field(3, ge=1, le=5, description="1 (highest) to 5 (lowest)")
    due_date: Optional[date] = Field(None, description="Optional due date")
    estimated_minutes: Optional[int] = Field(30, ge=5, le=600)
    category: Optional[str] = Field(None, description="work, personal, home, etc.")


class Routine(BaseModel):
    name: str
    steps: List[str] = Field(default_factory=list)
    preferred_time: Optional[str] = Field(None, description="morning/afternoon/evening/night")
    days: List[str] = Field(default_factory=lambda: ["Mon", "Tue", "Wed", "Thu", "Fri"]) 


class Pantryitem(BaseModel):
    name: str
    quantity: Optional[str] = Field(None, description="e.g., 2 cans, 500g, 1 pack")
    category: Optional[str] = Field(None, description="produce, dairy, pantry, frozen, etc.")


class Meal(BaseModel):
    title: str
    ingredients: List[str] = Field(..., description="List of ingredient names")
    steps: Optional[List[str]] = Field(default=None)
    tags: List[str] = Field(default_factory=list)


class Bill(BaseModel):
    name: str
    amount: float
    due_day: int = Field(..., ge=1, le=28, description="Day of month bill is due")
    autopay: bool = Field(False)


class Subscription(BaseModel):
    name: str
    amount: float
    cycle: str = Field("monthly", description="monthly|yearly")
    next_renewal: Optional[date] = None


class Shoppinglistitem(BaseModel):
    name: str
    needed_for: Optional[str] = None
    quantity: Optional[str] = None


class Checkin(BaseModel):
    date: date
    mood: Optional[str] = Field(None, description="e.g., calm, stressed, happy")
    energy: Optional[int] = Field(5, ge=1, le=10)
    notes: Optional[str] = None


class User(BaseModel):
    name: str
    email: EmailStr
    timezone: Optional[str] = None

