from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    role_code: str


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=64)
    password: str | None = Field(default=None, min_length=6, max_length=128)
    role_code: str | None = None
    is_active: bool | None = None


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

