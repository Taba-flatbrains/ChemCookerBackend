import os
from typing import Annotated, Union, List, Optional, Dict
from uuid import uuid4
from NetTypes import *
from Quest import *
from Chemical import STR_START_CHEMS, Chemical

from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH")
DOMAIN = os.getenv("DOMAIN", "localhost")

in_production = os.getenv("PRODUCTION", "true").lower() != "false"


from fastapi import FastAPI, Depends, Cookie, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Field, Session, SQLModel, create_engine, select, ARRAY, Field, Column, String, select, JSON
from pydantic import BaseModel
import hashlib

from passlib.hash import pbkdf2_sha256

app = FastAPI()

if not in_production:
    origins = [
        "http://localhost:4200",
        "http://localhost:34475", # for testing purposes
        "http://10.183.109.33:4200", # henni pc
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    origins = [
        "https://www.chemcooker.com",
        "http://www.chemcooker.com"
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
    skilltree: str = "" # string of skilltree node ids seperated by ;
    unlocked_chemicals: str # string of smiles seperated by ;
    nicknames: Dict = Field(default_factory=dict, sa_column=Column(JSON)) # dict of smiles to nicknames
    token: Optional[str] = None
    completed_quests: str = "" # string of quest ids seperated by ;
    pending_reactions: str = "" # smile1;smiles2;...!temp!uv    seperated by | for multiple pending reactions

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

class SkilltreeNode(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str
    x: int # relative pos to start
    y: int # relative pos to start
    neighbors : str # id seperated by ; unsure if I actually want to use this
    chem_rewards : Optional[str] # smiles seperated by ;
    misc_rewards : Optional[str] # unlucking mechanisc oder so
    misc_reward_icon : Optional[str] # url to img, if no chem is awarded use this
    skillpoint_cost : int = 1 

class PendingReaction(SQLModel, table=True):
    inputs : str = Field(primary_key=True) # string of smiles seperated by ;

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
database_url = os.getenv("DATABASE_URL", sqlite_url)  # Use DATABASE_URL from .env if available, otherwise use sqlite_url

connect_args = {}
if database_url.startswith("sqlite://"):
    connect_args["check_same_thread"] = False
engine = create_engine(database_url, connect_args=connect_args)

SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]



# post requests
@app.post("/signup")
def signup(r: SignupRequest, session: SessionDep, response : Response) -> SignupResponse:
    token = str(uuid4())
    session.add(User(
        name=r.username,
        email=r.email,
        password=pbkdf2_sha256.hash(r.password), # check: pbkdf2_sha256.verify("toomanysecrets", hash)
        skillpoints=0,
        skilltree="1", 
        unlocked_chemicals=STR_START_CHEMS,
        token=hashlib.sha256(token.encode('utf-8')).hexdigest(), # todo: add expire date
        nicknames={}
    ))
    session.commit()
    response.set_cookie(key="token", value=token, httponly=False, samesite="strict", expires=60*60*24*7, domain=DOMAIN)
    return SignupResponse(success=True, name=r.username, token=token)

@app.post("/login")
def login(r: LoginRequest, session: SessionDep, response:Response) -> LoginResponse:
    user = session.get(User, r.email)
    if (user is None):
        return LoginResponse(token="", success=False)
    hashed_pw = user.password
    if (pbkdf2_sha256.verify(r.password, hashed_pw)):
        token = str(uuid4())
        user.token = hashlib.sha256(token.encode('utf-8')).hexdigest()
        session.add(user) # is this correct? or does user get doubled
        session.commit()
        response.set_cookie(key="token", value=token, httponly=False, samesite="strict", expires=60*60*24*7, domain=DOMAIN)
        return LoginResponse(token=token, name=user.name, success=True)
    return LoginResponse(token="", success=False)

@app.post("/admin-login")
def admin_login(r: AdminLoginRequest, session: SessionDep, response:Response) -> AdminLoginResponse:
    if not pbkdf2_sha256.verify(r.password, ADMIN_PASSWORD_HASH):
        return AdminLoginResponse(success=False)
    token = str(uuid4())
    session.add(AdminToken(token=hashlib.sha256(token.encode('utf-8')).hexdigest()))
    session.commit()
    response.set_cookie(key="admin_token", value=token, httponly=False, samesite="strict", expires=60*60*24*7, domain=DOMAIN)
    return AdminLoginResponse(success=True, token=token)

@app.post("/set-default-chemical-identifiers")  
def set_default_chemical_identifiers(admin_token: Annotated[str | None, Cookie()], r: SetDefaultChemicalIdentifiersRequest, session: SessionDep):
    admin = session.get(AdminToken, hashlib.sha256(admin_token.encode('utf-8')).hexdigest()) # check for valid admin session
    if admin is None:
        raise HTTPException(status_code=404, detail="Admin token invalid")
    session.add(ChemicalDefaultIdentifiers(smile=r.smile, iupac=r.iupac, nickname=r.nickname)) # todo: set option to override previous default identifier
    session.commit()
    return

@app.post("/change-default-chemical-identifiers")
def change_default_chemical_identifiers(admin_token: Annotated[str | None, Cookie()], r: ChangeDefaultChemicalIdentifiersRequest, session: SessionDep):
    admin = session.get(AdminToken, hashlib.sha256(admin_token.encode('utf-8')).hexdigest()) # check for valid admin session
    if admin is None:
        raise HTTPException(status_code=404, detail="Admin token invalid")
    if r.old_smile == "":
        raise HTTPException(status_code=402, detail="Old smile empty")
    
    session.delete(session.get(ChemicalDefaultIdentifiers, r.old_smile))
    session.add(ChemicalDefaultIdentifiers(smile=r.new_smile, iupac=r.new_iupac, nickname=r.new_nickname))

    # todo: change smile in all places
    if r.old_smile != r.new_smile:
        reactions = session.exec(select(Reaction).where((Reaction.inputs.like(f"%{r.old_smile}%")) | (Reaction.outputs.like(f"%{r.old_smile}%")))).all()
        for reaction in reactions:
            reaction.inputs = reaction.inputs.replace(r.old_smile, r.new_smile)
            # sort reaction inputs
            reaction.inputs = ";".join(sorted(reaction.inputs.split(";")))
            reaction.outputs = reaction.outputs.replace(r.old_smile, r.new_smile)
            session.add(reaction)
        
        pending_reactions = session.exec(select(PendingReaction).where(PendingReaction.inputs.like(f"%{r.old_smile}%"))).all()
        for pending_reaction in pending_reactions:
            pending_reaction.inputs = pending_reaction.inputs.replace(r.old_smile, r.new_smile)
            session.add(pending_reaction)

        users = session.exec(select(User)).all()
        for user in users:
            user.unlocked_chemicals = user.unlocked_chemicals.replace(r.old_smile, r.new_smile)
            if r.old_smile in user.nicknames:
                user.nicknames[r.new_smile] = user.nicknames.pop(r.old_smile) # change nickname key to new smile
            user.pending_reactions = user.pending_reactions.replace(r.old_smile, r.new_smile)
            session.add(user)
        
        quests = session.exec(select(Quest)).all()
        for quest in quests:
            quest.condition_value = quest.condition_value.replace(r.old_smile, r.new_smile)
            if quest.reward_misc is not None:
                quest.reward_misc = quest.reward_misc.replace(r.old_smile, r.new_smile) # reward misc unused right now but feels right to add this
            session.add(quest) 

        skilltree_nodes = session.exec(select(SkilltreeNode)).all()
        for skilltree_node in skilltree_nodes:
            skilltree_node.chem_rewards = skilltree_node.chem_rewards.replace(r.old_smile, r.new_smile)
            session.add(skilltree_node)

    session.commit()
    return

@app.post("/set-nickname")
def set_nickname(token: Annotated[str | None, Cookie()], r: SetNicknameRequest, session: SessionDep):
    try:
        user = session.exec(select(User).where(User.token == hashlib.sha256(token.encode('utf-8')).hexdigest())).one() # if no error is thrown session is valid
    except:
        raise HTTPException(status_code=404, detail="User not found, login and signin seemed to have failed / token missing")
    nicknames = user.nicknames.copy()
    nicknames[r.smile] = r.nickname
    print(nicknames)
    user.nicknames = nicknames
    session.add(user)
    session.commit()
    return {"success":True}

@app.post("/submitreaction")  # todo: add option to change reaction
def submit_reaction(admin_token: Annotated[str | None, Cookie()], r: SubmitReactionRequest, session: SessionDep):
    admin = session.get(AdminToken, hashlib.sha256(admin_token.encode('utf-8')).hexdigest()) 
    if admin is None:
        raise HTTPException(status_code=404, detail="Admin token invalid")
    
    if len(r.inputs) == 0 or len(r.inputs) != len(set([chem["smile"] for chem in r.inputs])):
        return {"success": False}# no chemicals or duplicate chemicals
    
    #before sorting remove pending reactions that match this reaction (they are not sorted either)
    pending_reaction = session.get(PendingReaction, ";".join([chem["smile"] for chem in r.inputs]))
    if pending_reaction is not None:
        session.delete(pending_reaction)
        session.commit()

    #sort inputs and outputs to have a consistent order
    r.inputs.sort(key=lambda chem: chem["smile"])
    r.outputs.sort(key=lambda chem: chem["smile"])
    session.add(Reaction(
        inputs=";".join([chem["smile"] for chem in r.inputs]),
        outputs=";".join([chem["smile"] for chem in r.outputs]),
        temp=r.temp,
        uv=r.uv))
    session.commit()

    return {"success": True}

lightSkilltreeNode = 18
@app.post("/cook")
def cook(token: Annotated[str | None, Cookie()], r: CookRequest, session: SessionDep) -> CookResponse:
    try:
        user = session.exec(select(User).where(User.token == hashlib.sha256(token.encode('utf-8')).hexdigest())).one() # if no error is thrown session is valid
    except:
        raise HTTPException(status_code=404, detail="User not found, login and signin seemed to have failed / token missing")
    if len(r.chemicals) == 0 or len(r.chemicals) != len(set(r.chemicals)):
        return CookResponse(success=False, products=[], new_chems=[]) # no chemicals or duplicate chemicals
    if r.uv:
        unlocked_skilltree_nodes = user.skilltree.split(";") if user.skilltree != "" else []
        if str(lightSkilltreeNode) not in unlocked_skilltree_nodes:
            return CookResponse(success=False, products=[], new_chems=[]) # uv not unlocked
    return _cook_internal(user, r, session, shouldAddPending=True)

def _cook_internal(user: User, r: CookRequest, session: SessionDep, shouldAddPending : bool = False) -> CookResponse:
    # check if user has the input chemicals
    user_chemicals = user.unlocked_chemicals.split(";")
    for chem in r.chemicals:
        if chem not in user_chemicals:
            return CookResponse(success=False, products=[], new_chems=[])
    # find matching reaction
    r.chemicals.sort()
    reactions = session.exec(select(Reaction).where(Reaction.inputs==";".join([chem for chem in r.chemicals]))).all()
    if len(reactions) == 0:
        if not shouldAddPending:
            return CookResponse(success=False, products=[], new_chems=[], added_to_pending=True) # reaction does not exist
        if session.get(PendingReaction, ";".join([chem for chem in r.chemicals])) is None:
            session.add(PendingReaction(inputs=";".join([chem for chem in r.chemicals]))) # add if not already existing
            session.commit()
        pr = user.pending_reactions.split("|") if user.pending_reactions != "" else []
        if not ";".join([chem for chem in r.chemicals]) + "!" + str(r.temp) + "!" + str(int(r.uv)) in pr:
            pr.append(";".join([chem for chem in r.chemicals]) + "!" + str(r.temp) + "!" + str(int(r.uv)))
            user.pending_reactions = "|".join(pr)
            session.add(user)
            session.commit()
        return CookResponse(success=False, products=[], new_chems=[], added_to_pending=True) # reaction does not exist yet
    already_completed_quests = user.completed_quests.split(";") if user.completed_quests != "" and not user.completed_quests is None else []
    for reaction in reactions:
        if reaction.temp - r.temp >= 0 and str(reaction.temp - r.temp).count("9") == 0 and reaction.uv == r.uv and reaction.outputs != "": # lazy way of validating temp
            # successful reaction
            output_chemicals = reaction.outputs.split(";")
            new_chems = []

            skillpoints_gained = 0
            quests_completed = []
            for chem in output_chemicals:
                if chem not in user_chemicals:
                    user_chemicals.append(chem)
                    new_chems.append(chem)
                completed_quests = session.exec(select(Quest).where(
                    (Quest.condition_type == QuestConditionTypes.OBTAIN_CHEMICAL) & 
                    (Quest.condition_value == chem)
                )).all() 
                for quest in completed_quests:
                    if (str(quest.id) in already_completed_quests):
                        continue # quest already completed
                    user.skillpoints += quest.reward_skillpoints
                    skillpoints_gained += quest.reward_skillpoints
                    quests_completed.append(quest.id)
                    already_completed_quests.append(str(quest.id))
            user.completed_quests = ";".join(already_completed_quests)
            user.unlocked_chemicals = ";".join(user_chemicals)
            session.add(user)
            session.commit()
            return CookResponse(success=True, 
                                inputs=r.chemicals,
                                temp=r.temp,
                                uv=r.uv,
                                products=[chem.to_dict() for chem in getChemsFromSmilesList(output_chemicals, session)], 
                                new_chems=[chem.to_dict() for chem in getChemsFromSmilesList(new_chems, session)],
                                skillpoints_gained=skillpoints_gained,
                                quests_completed=quests_completed)

    return CookResponse(success=False, products=[], new_chems=[]) # reaction not found

@app.post("/submitquest")
def submit_quest(admin_token: Annotated[str | None, Cookie()], r: SubmitQuestRequest, session: SessionDep) -> SubmitQuestResponse:
    admin = session.get(AdminToken, hashlib.sha256(admin_token.encode('utf-8')).hexdigest()) 
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

@app.post("/change-quest")
def change_quest(admin_token: Annotated[str | None, Cookie()], r: ChangeQuestRequest, session: SessionDep) -> ChangeQuestResponse:
    admin = session.get(AdminToken, hashlib.sha256(admin_token.encode('utf-8')).hexdigest())
    if admin is None:
        raise HTTPException(status_code=404, detail="Admin token invalid")
    quest = session.get(Quest, r.id)
    if quest is None:
        raise HTTPException(status_code=404, detail="Quest not found")
    quest.description = r.description
    quest.reward_skillpoints = r.reward_skillpoints
    quest.reward_misc = r.reward_misc
    quest.condition_type = r.condition_type
    quest.condition_value = r.condition_value
    session.add(quest)
    session.commit()
    return ChangeQuestResponse(success=True)

@app.post("/submitskilltreenode")
def submit_skilltreenode(admin_token: Annotated[str | None, Cookie()], r: SubmitSkilltreeNodeRequest, session: SessionDep) -> SubmitSkilltreeNodeResponse:
    admin = session.get(AdminToken, hashlib.sha256(admin_token.encode('utf-8')).hexdigest()) 
    if admin is None:
        raise HTTPException(status_code=404, detail="Admin token invalid")
    # todo: check if a node already exists on x and y
    neighbors = []
    for offset in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
        try:
            neighbor = session.exec(select(SkilltreeNode).where(SkilltreeNode.x == r.x + offset[0],
                                                                SkilltreeNode.y == r.y + offset[1])).one()
            neighbors.append(str(neighbor.id))
        except:
            pass
    new_node = SkilltreeNode(
        title = r.title,
        description = r.description,
        x = r.x,
        y = r.y,
        neighbors = ";".join(neighbors),
        chem_rewards = ";".join(r.chem_rewards),
        misc_rewards = ";".join(r.misc_rewards), # unlucking mechanisc oder so
        misc_reward_icon = r.misc_reward_icon, # url to img, if no chem is awarded use this
        skillpoint_cost = r.skillpoint_cost
    )
    session.add(new_node)
    session.commit()
    session.refresh(new_node)
    for neighbor_id in neighbors:
        neighbor_object = session.get(SkilltreeNode, int(neighbor_id))
        neighbor_neighbors = neighbor_object.neighbors.split(";") if neighbor_object.neighbors != "" else []
        neighbor_neighbors.append(str(new_node.id))
        neighbor_object.neighbors = ";".join(neighbor_neighbors)
        session.add(neighbor_object)
    session.commit()

    return SubmitSkilltreeNodeResponse(success=True)

@app.post("/skilltree-upgrade")
def skilltreeUpgrade(token: Annotated[str | None, Cookie()], r: SkilltreeUpgradeRequest, session: SessionDep) -> SkilltreeUpgradeResponse: # stupid name but I dont know what to call it
    try:
        user = session.exec(select(User).where(User.token == hashlib.sha256(token.encode('utf-8')).hexdigest())).one() # if no error is thrown session is valid
    except:
        raise HTTPException(status_code=404, detail="User not found, login and signin seemed to have failed / token missing")
    node = session.get(SkilltreeNode, r.id)
    if user.skillpoints >= node.skillpoint_cost:
        user.skillpoints = user.skillpoints - node.skillpoint_cost
    else:
        return {"success":False}
    unlocked_skilltree_nodes = user.skilltree.split(";")
    temp = False
    for neighbor_id in node.neighbors.split(";"):
        if str(neighbor_id) in unlocked_skilltree_nodes:
            temp = True
            break
    if not temp:
        return {"success":False} # node is not connected to already unlocked node
    unlocked_skilltree_nodes.append(str(r.id))
    user.skilltree = ";".join(unlocked_skilltree_nodes)
    session.commit()
    unlocked_chemicals = []
    if node.chem_rewards is not None:
        for chem_smile in node.chem_rewards.split(";"):
            user_chemicals = user.unlocked_chemicals.split(";")
            if chem_smile not in user_chemicals:
                user_chemicals.append(chem_smile)
                unlocked_chemicals.append(chem_smile)
            user.unlocked_chemicals = ";".join(user_chemicals)
        session.commit()
    return {"success":True, "unlocked_chemicals":[chem.to_dict() for chem in getChemsFromSmilesList(unlocked_chemicals, session)]}

# get requests
@app.get("/validatetoken") 
def validatetoken(token: Annotated[str | None, Cookie()], session: SessionDep) -> ValidTokenResponse:
    try:
        user = session.exec(select(User).where(User.token == hashlib.sha256(token.encode('utf-8')).hexdigest())).one() # if no error is thrown session is valid
    except:
        return ValidTokenResponse(valid=False)
    return ValidTokenResponse(valid=True, name=user.name)

@app.get("/admin-validatetoken") # todo: delete old expired tokens
def admin_validatetoken(admin_token: Annotated[str | None, Cookie()], session: SessionDep) -> ValidTokenResponse:
    admin = session.get(AdminToken, hashlib.sha256(admin_token.encode('utf-8')).hexdigest()) 
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
        chemicals[smiles.index(nickname_key)].nickname = nicknames[nickname_key] # ultra inefficient should change later

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
def getAllChems(admin_token: Annotated[str | None, Cookie()], session: SessionDep) -> AvailableChemsResponse: 
    admin = session.get(AdminToken, hashlib.sha256(admin_token.encode('utf-8')).hexdigest()) 
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

@app.get("/skilltree")
def getSkilltree(token: Annotated[str | None, Cookie()], session: SessionDep) -> GetSkilltreeResponse:
    try:
        user = session.exec(select(User).where(User.token == hashlib.sha256(token.encode('utf-8')).hexdigest())).one() # if no error is thrown session is valid
        unlocked_skilltree_nodes = user.skilltree.split(";") if user.skilltree != "" else []
        availableSkillpoints = user.skillpoints
    except:
        unlocked_skilltree_nodes = []
        availableSkillpoints = 0
    all_skilltree_nodes = session.exec(select(SkilltreeNode)).all()

    return GetSkilltreeResponse(
        skilltree_nodes=[{
            "id":node.id,
            "title":node.title,
            "description":node.description,
            "x":node.x,
            "y":node.y,
            "neighbors":[int(neighbor_id) for neighbor_id in node.neighbors.split(";")] if node.neighbors != "" else [],
            "chem_rewards":node.chem_rewards.split(";") if node.chem_rewards != "" else [],
            "misc_rewards":node.misc_rewards.split(";") if node.misc_rewards != "" else [],
            "misc_reward_icon":node.misc_reward_icon,
            "skillpoint_cost":node.skillpoint_cost
        } for node in all_skilltree_nodes],
        unlocked_skilltree_nodes=[int(node_id) for node_id in unlocked_skilltree_nodes],
        availableSkillpoints=availableSkillpoints
    )

@app.get("/pending-reactions")
def get_pending_reactions(token: Annotated[str | None, Cookie()], session: SessionDep) -> GetPendingReactionsResponse:
    try:
        user = session.exec(select(User).where(User.token == hashlib.sha256(token.encode('utf-8')).hexdigest())).one() # if no error is thrown session is valid
    except:
        raise HTTPException(status_code=404, detail="User not found, login and signin seemed to have failed / token missing")
    pending_reactions = []
    successful_pending_reactions = []
    removed_pending_reactions = []
    upr = user.pending_reactions
    new_upr = []
    if upr != "":
        for pr in upr.split("|"):
            parts = pr.split("!")
            inputs = parts[0].split(";")
            
            # check if reaction has been resolved
            cook_response = _cook_internal(user, CookRequest(chemicals=inputs, temp=int(parts[1]), uv=bool(int(parts[2]))), session)
            if cook_response.success:
                successful_pending_reactions.append(cook_response)
                continue # reaction has been resolved successfully, do not add to pending reactions
            
            temp = int(parts[1])
            uv = bool(int(parts[2]))
            if not cook_response.added_to_pending:
                removed_pending_reactions.append({
                "inputs":inputs,
                "temp":temp,
                "uv":uv
                })
                continue # reaction now added but was executed without success
            pending_reactions.append({
                "inputs":inputs,
                "temp":temp,
                "uv":uv
            })
            new_upr.append(pr) # keep in pending reactions, resolved reactions are removed
    user.pending_reactions = "|".join(new_upr)
    session.add(user)
    session.commit()

    return GetPendingReactionsResponse(
        pending_reactions=pending_reactions,
        removed_pending_reactions=removed_pending_reactions,
        successful_pending_reactions=successful_pending_reactions
    )

@app.get("/admin-pending-reactions")
def admin_get_pending_reactions(admin_token: Annotated[str | None, Cookie()], session: SessionDep) -> AdminGetPendingReactionsResponse:
    admin = session.get(AdminToken, hashlib.sha256(admin_token.encode('utf-8')).hexdigest()) 
    if admin is None:
        raise HTTPException(status_code=404, detail="Admin token invalid")
    pending_reactions = session.exec(select(PendingReaction)).all()
    return AdminGetPendingReactionsResponse(
        pending_reactions=[pr.inputs.split(";") for pr in pending_reactions]
    )