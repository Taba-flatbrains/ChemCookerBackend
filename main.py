from typing import Annotated, Union, List, Optional
from uuid import uuid4
from NetTypes import (
    SignupRequest, 
    SignupResponse,
    LoginRequest,
    LoginResponse,
    ValidTokenResponse
)
from Chemical import STR_START_CHEMS

from fastapi import FastAPI, Depends, Cookie
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Field, Session, SQLModel, create_engine, select, ARRAY, Field, Column, String, select
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
    skilltree: str # JSON string representing the skill tree
    unlocked_chemicals: str # array string of "{'smiles': string, 'iupac': string, 'nickname': string}" seperated by ;
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
        skilltree="{}", # Placeholder
        unlocked_chemicals=STR_START_CHEMS,
        token=hashlib.sha256(token.encode('utf-8')).hexdigest() # todo: add expire date
    ))
    session.commit()
    return SignupResponse(success=True, token=token)

@app.post("/login/")
def login(r: LoginRequest, session: SessionDep) -> LoginResponse:
    user = session.get(User, r.email)
    hashed_pw = user.password
    if (pbkdf2_sha256.verify(r.password, hashed_pw)):
        token = str(uuid4())
        user.token = pbkdf2_sha256.hash(token)
        session.add(user)
        session.commit() # todo: check if updating token works like this
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