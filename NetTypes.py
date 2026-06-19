from pydantic import BaseModel
from typing import Optional


class SignupRequest(BaseModel):
    username: str
    email: str
    password: str
class SignupResponse(BaseModel):
    success: bool
    token: str
    name: Optional[str] = None

class LoginRequest(BaseModel):
    email: str 
    password: str
class LoginResponse(BaseModel):
    success: bool
    token: str
    name: Optional[str] = None

class ValidTokenResponse(BaseModel):
    valid: bool
    name: Optional[str] = None

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

class ChangeDefaultChemicalIdentifiersRequest(BaseModel):
    old_smile : str
    new_smile : str
    new_iupac : str
    new_nickname : str

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
    inputs: Optional[list[str]] = None
    temp: Optional[int] = None
    uv: Optional[bool] = None
    products: list[dict]
    new_chems: Optional[list[dict]] = None
    skillpoints_gained: int = 0
    quests_completed: list[int] = [] # quest ids
    added_to_pending: bool = False

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

class SubmitSkilltreeNodeRequest(BaseModel):
    description: str
    title: str
    x: int # relative pos to start
    y: int # relative pos to start
    chem_rewards : list[str] # smiles seperated by ;
    misc_rewards : list[str] # unlucking mechanisc oder so
    misc_reward_icon : Optional[str] # url to img, if no chem is awarded use this
    skillpoint_cost : int = 1 
class SubmitSkilltreeNodeResponse(BaseModel):
    success: bool

class GetSkilltreeResponse(BaseModel):
    skilltree_nodes : list[dict]
    unlocked_skilltree_nodes : list[int]
    availableSkillpoints : int

class SkilltreeUpgradeRequest(BaseModel):
    id : int
class SkilltreeUpgradeResponse(BaseModel):
    success : bool
    unlocked_chemicals : Optional[list[dict]] = None

class SetNicknameRequest(BaseModel):
    smile : str
    nickname : str

class GetPendingReactionsResponse(BaseModel):
    pending_reactions : list[dict]
    removed_pending_reactions : list[dict] # list of reactions that were removed because they were invalid
    successful_pending_reactions : list[CookResponse] # list of reactions that were successful
    # this should be called regularly and on startup, if a reaction has been successful popup should be shown

class AdminGetPendingReactionsResponse(BaseModel):
    pending_reactions : list[list[str]]