from typing import Annotated, Union, List, Optional, Dict
from uuid import uuid4
from NetTypes import *
from Quest import *
from Chemical import STR_START_CHEMS, Chemical
from hidden_constants import ADMIN_PASSWORD_HASH

from fastapi import FastAPI, Depends, Cookie, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Field, Session, SQLModel, create_engine, select, ARRAY, Field, Column, String, select, JSON
from pydantic import BaseModel
import hashlib

from passlib.hash import pbkdf2_sha256

app = FastAPI()

origins = [
    "http://localhost:4200",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# tables
class User(SQLModel, table=True):
    name: str
    email: str = Field(primary_key=True)
    password: str
    skillpoints: int
    skilltree: Dict = Field(default_factory=dict, sa_column=Column(JSON)) # dict placeholder
    unlocked_chemicals: str # string of smiles seperated by ;
    nicknames: Dict = Field(default_factory=dict, sa_column=Column(JSON)) # dict of smiles to nicknames
    token: Optional[str] = None
    completed_quests: str = "" # string of quest ids seperated by ;

class AdminToken(SQLModel, table=True):
    token: str = Field(primary_key=True) # todo: set expire date

class Reaction(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    inputs: str # string of smiles seperated by ;
    outputs: str # string of smiles seperated by ;
    temp: int # 4 "bits": XXXX, 0001: cold, 0010: rt, 0100: reflux, 1000: pyrolysis, multiple can be set
    uv: bool # on/off
    description: Optional[str] = None

class ChemicalDefaultIdentifiers(SQLModel, table=True):
    smile: str = Field(primary_key=True)
    iupac: str 
    nickname : str

class Quest(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    description: str
    reward_skillpoints: int
    reward_misc: Optional[str] = None # maybe special chemical or so
    condition_type: str # "obtain_chemical", ...
    condition_value: str # smile for "obtain_chemical", ...


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)

SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]



# post requests
@app.post("/signup/")
def signup(r: SignupRequest, session: SessionDep) -> SignupResponse:
    token = str(uuid4())
    session.add(User(
        name=r.username,
        email=r.email,
        password=pbkdf2_sha256.hash(r.password), # check: pbkdf2_sha256.verify("toomanysecrets", hash)
        skillpoints=0,
        skilltree={}, # Placeholder
        unlocked_chemicals=STR_START_CHEMS,
        token=hashlib.sha256(token.encode('utf-8')).hexdigest(), # todo: add expire date
        nicknames={}
    ))
    session.commit()
    return SignupResponse(success=True, token=token)

@app.post("/login/")
def login(r: LoginRequest, session: SessionDep) -> LoginResponse:
    user = session.get(User, r.email)
    hashed_pw = user.password
    if (pbkdf2_sha256.verify(r.password, hashed_pw)):
        token = str(uuid4())
        user.token = hashlib.sha256(token.encode('utf-8')).hexdigest()
        session.add(user) # is this correct? or does user get doubled
        session.commit()
        return LoginResponse(token=token, success=True)
    return LoginResponse(token="", success=False)

@app.post("/admin-login")
def admin_login(r: AdminLoginRequest, session: SessionDep) -> AdminLoginResponse:
    if not pbkdf2_sha256.verify(r.password, ADMIN_PASSWORD_HASH):
        return AdminLoginResponse(success=False)
    token = str(uuid4())
    session.add(AdminToken(token=hashlib.sha256(token.encode('utf-8')).hexdigest()))
    session.commit()
    return AdminLoginResponse(success=True, token=token)

@app.post("/set-default-chemical-identifiers")  # todo: add option to change nickname
def set_default_chemical_identifiers(token: Annotated[str | None, Cookie()], r: SetDefaultChemicalIdentifiersRequest, session: SessionDep):
    admin = session.get(AdminToken, hashlib.sha256(token.encode('utf-8')).hexdigest()) # check for valid admin session
    if admin is None:
        raise HTTPException(status_code=404, detail="Admin token invalid")
    session.add(ChemicalDefaultIdentifiers(smile=r.smile, iupac=r.iupac, nickname=r.nickname)) # todo: set option to override previous default identifier
    session.commit()
    return

@app.post("/submitreaction")  # todo: add option to change reaction
def submit_reaction(token: Annotated[str | None, Cookie()], r: SubmitReactionRequest, session: SessionDep):
    admin = session.get(AdminToken, hashlib.sha256(token.encode('utf-8')).hexdigest()) 
    if admin is None:
        raise HTTPException(status_code=404, detail="Admin token invalid")
    #sort inputs and outputs to have a consistent order
    r.inputs.sort(key=lambda chem: chem["smile"])
    r.outputs.sort(key=lambda chem: chem["smile"])
    session.add(Reaction(
        inputs=";".join([chem["smile"] for chem in r.inputs]),
        outputs=";".join([chem["smile"] for chem in r.outputs]),
        temp=r.temp,
        uv=r.uv))
    session.commit()

@app.post("/cook")
def cook(token: Annotated[str | None, Cookie()], r: CookRequest, session: SessionDep) -> CookResponse:
    try:
        user = session.exec(select(User).where(User.token == hashlib.sha256(token.encode('utf-8')).hexdigest())).one() # if no error is thrown session is valid
    except:
        raise HTTPException(status_code=404, detail="User not found, login and signin seemed to have failed / token missing")
    
    # check if user has the input chemicals
    user_chemicals = user.unlocked_chemicals.split(";")
    for chem in r.chemicals:
        if chem not in user_chemicals:
            return CookResponse(success=False, products=[], new_chems=[])

    # find matching reaction
    r.chemicals.sort()
    reactions = session.exec(select(Reaction).where(Reaction.inputs==";".join([chem for chem in r.chemicals]))).all()
    for reaction in reactions:
        print(reaction.temp - r.temp >= 0 and str(reaction.temp - r.temp).count("9") == 0)
        if reaction.temp - r.temp >= 0 and str(reaction.temp - r.temp).count("9") == 0 and reaction.uv == r.uv: # lazy way of validating temp
            # successful reaction
            output_chemicals = reaction.outputs.split(";")
            new_chems = []

            skillpoints_gained = 0
            already_completed_quests = user.completed_quests.split(";") if user.completed_quests != "" and not user.completed_quests is None else []
            quests_completed = []
            for chem in output_chemicals: # todo: check if this completes quest
                if chem not in user_chemicals:
                    user_chemicals.append(chem)
                    new_chems.append(chem)
                completed_quests = session.exec(select(Quest).where(
                    (Quest.condition_type == QuestConditionTypes.OBTAIN_CHEMICAL) & 
                    (Quest.condition_value == chem)
                )).all() # todo: give reward
                for quest in completed_quests:
                    if (str(quest.id) in already_completed_quests):
                        continue # quest already completed
                    user.skillpoints += quest.reward_skillpoints
                    skillpoints_gained += quest.reward_skillpoints
                    quests_completed.append(quest.id)
            user.unlocked_chemicals = ";".join(user_chemicals)
            session.add(user)
            session.commit()
            return CookResponse(success=True, products=[chem.to_dict() for chem in getChemsFromSmilesList(output_chemicals, session)], 
                                new_chems=[chem.to_dict() for chem in getChemsFromSmilesList(new_chems, session)],
                                skillpoints_gained=skillpoints_gained,
                                quests_completed=quests_completed)
    
    return CookResponse(success=False, products=[], new_chems=[]) # reaction not found

@app.post("/submitquest")
def submit_quest(token: Annotated[str | None, Cookie()], r: SubmitQuestRequest, session: SessionDep) -> SubmitQuestResponse:
    admin = session.get(AdminToken, hashlib.sha256(token.encode('utf-8')).hexdigest()) 
    if admin is None:
        raise HTTPException(status_code=404, detail="Admin token invalid")
    session.add(Quest(
        description=r.description,
        reward_skillpoints=r.reward_skillpoints,
        reward_misc=r.reward_misc,
        condition_type=r.condition_type,
        condition_value=r.condition_value
    ))
    session.commit()
    return SubmitQuestResponse(success=True)


# get requests
@app.get("/validatetoken") 
def validatetoken(token: Annotated[str | None, Cookie()], session: SessionDep) -> ValidTokenResponse:
    try:
        user = session.exec(select(User).where(User.token == hashlib.sha256(token.encode('utf-8')).hexdigest())).one() # if no error is thrown session is valid
    except:
        return ValidTokenResponse(valid=False)
    return ValidTokenResponse(valid=True)

@app.get("/admin-validatetoken")
def admin_validatetoken(token: Annotated[str | None, Cookie()], session: SessionDep) -> ValidTokenResponse:
    admin = session.get(AdminToken, hashlib.sha256(token.encode('utf-8')).hexdigest()) 
    if admin is None:
        return ValidTokenResponse(valid=False)
    return ValidTokenResponse(valid=True)

@app.get("/availablechems")
def getAvailableChems(token: Annotated[str | None, Cookie()], session: SessionDep) -> AvailableChemsResponse:
    try:
        user = session.exec(select(User).where(User.token == hashlib.sha256(token.encode('utf-8')).hexdigest())).one() # if no error is thrown session is valid
    except:
        raise HTTPException(status_code=404, detail="User not found, login and signin seemed to have failed / token missing")
    
    smiles = user.unlocked_chemicals.split(";")
    chemicals = getChemsFromSmilesList(smiles, session)

    # change nickname
    nicknames = user.nicknames
    for nickname_key in nicknames.keys(): # todo: add error catching (if nickname is set for chemical not obtained)
        chemicals[nickname_key].nickname = nicknames[nickname_key]

    return {"chemicals":list([chemical.to_dict() for chemical in chemicals])}

def getChemsFromSmilesList(smiles: List[str], session: SessionDep) -> List[Chemical]:
    default_identifiers : list[ChemicalDefaultIdentifiers] = []
    for smile in smiles:
        default_identifiers.append(session.get(ChemicalDefaultIdentifiers, smile))
        if (default_identifiers[-1] is None):
            default_identifiers[-1] = ChemicalDefaultIdentifiers(iupac=":(", nickname=":(")
    chemicals = [Chemical(smiles[i], default_identifiers[i].iupac, default_identifiers[i].nickname) for i in range(len(smiles))]
    return chemicals

@app.get("/all-chems") # admin only
def getAllChems(token: Annotated[str | None, Cookie()], session: SessionDep) -> AvailableChemsResponse: 
    admin = session.get(AdminToken, hashlib.sha256(token.encode('utf-8')).hexdigest()) 
    if admin is None:
        raise HTTPException(status_code=404, detail="Admin token invalid")
    
    all_default_identifiers = session.exec(select(ChemicalDefaultIdentifiers)).all()
    chemicals = [Chemical(chem.smile, chem.iupac, chem.nickname) for chem in all_default_identifiers]
    return {"chemicals":list([chemical.to_dict() for chemical in chemicals])}

@app.get("/all-quests")
def getAllQuests(token: Annotated[str | None, Cookie()], session: SessionDep) -> AllQuestsResponse:
    try:
        user = session.exec(select(User).where(User.token == hashlib.sha256(token.encode('utf-8')).hexdigest())).one() # if no error is thrown session is valid
        completed_quests = user.completed_quests.split(";") if user.completed_quests != "" and not user.completed_quests is None else []
    except:
        completed_quests = []
    
    all_quests = session.exec(select(Quest)).all()
    return AllQuestsResponse(
        quests=[{
            "id": quest.id,
            "description": quest.description,
            "reward_skillpoints": quest.reward_skillpoints,
            "reward_misc": quest.reward_misc,
            "condition_type": quest.condition_type,
            "condition_value": quest.condition_value
        } for quest in all_quests],
        completed_quests=[int(qid) for qid in completed_quests]
    )
