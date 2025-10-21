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

class AvailableChemsResponse(BaseModel):
    chemicals: list[dict]

class AdminLoginRequest(BaseModel):
    password: str
class AdminLoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None

class SetDefaultChemicalIdentifiersRequest(BaseModel):
    smile : str
    iupac : str
    nickname : str

class SubmitReactionRequest(BaseModel):
    inputs: list[dict]
    outputs: list[dict]
    temp: int
    uv : bool

class CookRequest(BaseModel):
    chemicals: list[str]
    temp: int
    uv: bool
class CookResponse(BaseModel):
    success: bool
    products: list[dict]
    new_chems: Optional[list[dict]] = None
    skillpoints_gained: int = 0
    quests_completed: list[int] = [] # quest ids

class AllQuestsResponse(BaseModel):
    quests: list[dict]
    completed_quests: list[int]

class SubmitQuestRequest(BaseModel):
    description: str
    reward_skillpoints: int
    reward_misc: Optional[str] = None # maybe special chemical or so
    condition_type: str # "obtain_chemical", ...
    condition_value: str # smile for "obtain_chemical", ...
class SubmitQuestResponse(BaseModel):
    success: bool