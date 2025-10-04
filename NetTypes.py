from pydantic import BaseModel


class SignupRequest(BaseModel):
    username: str
    email: str
    password: str
class SignupResponse(BaseModel):
    success: bool
    token: str