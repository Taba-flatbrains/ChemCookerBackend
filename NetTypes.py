from pydantic import BaseModel


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str
class SignupResponse(BaseModel):
    success: bool
    token: str