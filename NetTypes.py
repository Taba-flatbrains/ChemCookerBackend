from pydantic import BaseModel
from typing import Optional


class SignupRequest(BaseModel):
    username: str
    email: str
    password: str
class SignupResponse(BaseModel):
    success: bool
    token: str

class LoginRequest(BaseModel):
    email: str 
    password: str
class LoginResponse(BaseModel):
    success: bool
    token: str

class ValidTokenResponse(BaseModel):
    valid: bool