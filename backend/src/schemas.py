
import re
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StrictBool,
    field_validator,
)


# Reject unsafe control characters.
# Allow normal tabs and newlines in descriptions and comments.
INVALID_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")

# ASVS 2.1: length-based policy, with a cap so huge inputs can't slow down Argon2
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128


def validate_text(value: str) -> str:
    if INVALID_CONTROL_CHARS.search(value):
        raise ValueError("Text contains invalid control characters")
    if "<" in value or ">" in value:
        raise ValueError("Angle brackets (< and >) are not allowed.")
    return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class ChangePasswordRequest(BaseModel):
    # CHANGE 1: Reject unexpected fields.
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    current_password: SecretStr = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    new_password: SecretStr = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class IncidentCreate(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    priority: Literal["high", "medium", "low"]

    # CHANGE 2: Validate incident text.
    @field_validator("title", "description")
    @classmethod
    def check_text(cls, value: str) -> str:
        return validate_text(value)


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[a-z0-9_]+$",
    )
    password: SecretStr = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    role: Literal["user", "reviewer", "admin"] = "user"


class IncidentStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["open", "under-review", "closed"]


class CommentCreate(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    text: str = Field(min_length=1, max_length=2000)

    # CHANGE 3: Validate comment text.
    @field_validator("text")
    @classmethod
    def check_text(cls, value: str) -> str:
        return validate_text(value)


class UserAccountUpdate(BaseModel):
    # CHANGE 4: Reject unexpected fields.
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "reviewer", "admin"]
    is_active: StrictBool
