from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool
from typing import Literal


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=128)


class IncidentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[a-z0-9_]+$",
    )
    password: SecretStr = Field(min_length=5, max_length=128)
    role: Literal["user", "reviewer", "admin"] = "user"


class IncidentStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["open", "under-review", "closed"]

class CommentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    text: str = Field(min_length=1, max_length=2000)

class UserRoleUpdate(BaseModel):
    role: Literal["user", "reviewer", "admin"]


class UserStatusUpdate(BaseModel):
    is_active: StrictBool