from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool
from typing import Literal


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=5, max_length=15)


class ChangePasswordRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    current_password: SecretStr = Field(min_length=5, max_length=15)
    new_password: SecretStr = Field(min_length=5, max_length=15)


class IncidentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    priority: Literal["high", "medium", "low"]


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[a-z0-9_]+$",
    )
    password: SecretStr = Field(min_length=5, max_length=15)
    role: Literal["user", "reviewer", "admin"] = "user"


class IncidentStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["open", "under-review", "closed"]


class CommentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    text: str = Field(min_length=1, max_length=2000)


class UserAccountUpdate(BaseModel):
    role: Literal["user", "reviewer", "admin"]
    is_active: StrictBool
