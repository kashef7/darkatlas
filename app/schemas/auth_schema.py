from pydantic import BaseModel, Field, ConfigDict
from app.models.user import Role


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class UserResponse(BaseModel):
    id: str
    username: str
    role: Role

    model_config = ConfigDict(from_attributes=True)
