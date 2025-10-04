from typing import Annotated, Union, List, Optional
from uuid import uuid4
from NetTypes import (
    SignupRequest, 
    SignupResponse
)
from Chemical import STR_START_CHEMS

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Field, Session, SQLModel, create_engine, select, ARRAY, Field, Column, String
from pydantic import BaseModel

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
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str
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
        name=r.name,
        email=r.email,
        password=r.password, # todo: hash password
        skillpoints=0,
        skilltree="{}", # Placeholder
        unlocked_chemicals=STR_START_CHEMS,
        token=token # todo hast token
    ))
    session.commit()
    return SignupResponse(success=True, token=token)