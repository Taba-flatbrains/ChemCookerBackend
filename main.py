from typing import Annotated, Union, List, Optional, Dict
from uuid import uuid4
from NetTypes import *
from Chemical import STR_START_CHEMS, Chemical

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


# get requests
@app.get("/validatetoken/") 
def validatetoken(token: Annotated[str | None, Cookie()], session: SessionDep) -> ValidTokenResponse:
    try:
        user = session.exec(select(User).where(User.token == hashlib.sha256(token.encode('utf-8')).hexdigest())).one() # if no error is thrown session is valid
    except:
        return ValidTokenResponse(valid=False)
    return ValidTokenResponse(valid=True)

@app.get("/availablechems")
def getAvailableChems(token: Annotated[str | None, Cookie()], session: SessionDep) -> AvailableChemsResponse:
    try:
        user = session.exec(select(User).where(User.token == hashlib.sha256(token.encode('utf-8')).hexdigest())).one() # if no error is thrown session is valid
    except:
        raise HTTPException(status_code=404, detail="User not found, login and signin seemed to have failed / token missing")
    
    smiles = user.unlocked_chemicals.split(";")
    chemicals = [Chemical(i) for i in smiles]

    # change nickname
    nicknames = user.nicknames
    for nickname_key in nicknames.keys(): # todo: add error catching (if nickname is set for chemical not obtained)
        chemicals[nickname_key].nickname = nicknames[nickname_key]

    return {"chemicals":list([chemical.to_dict() for chemical in chemicals])}


