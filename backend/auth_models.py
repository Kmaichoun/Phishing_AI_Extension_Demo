from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, SecretStr, field_validator


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: SecretStr = Field(min_length=12, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("ชื่อผู้ใช้ต้องมีอย่างน้อย 3 ตัวอักษร")
        if "@" in value or any(character.isspace() for character in value):
            raise ValueError("ชื่อผู้ใช้ต้องไม่มีช่องว่างหรือเครื่องหมาย @")
        return value



class LoginRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("identifier")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("ข้อมูลนี้ห้ามเว้นว่าง")
        return value


class ProfileUpdateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    current_password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("ชื่อผู้ใช้ต้องมีอย่างน้อย 3 ตัวอักษร")
        if "@" in value or any(character.isspace() for character in value):
            raise ValueError("ชื่อผู้ใช้ต้องไม่มีช่องว่างหรือเครื่องหมาย @")
        return value


class PasswordChangeRequest(BaseModel):
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=12, max_length=128)


class UserResponse(BaseModel):
    user_id: int
    username: str
    email: str
    role: Literal["user", "admin"]


class PasswordChangeResponse(BaseModel):
    ok: bool
    other_sessions_revoked: int
