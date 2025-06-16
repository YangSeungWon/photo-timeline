from pydantic import BaseModel, EmailStr


class UserRegister(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str
    display_name: str


class UserLogin(BaseModel):
    """User login request."""

    email: EmailStr
    password: str


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token payload data."""

    user_id: str | None = None
