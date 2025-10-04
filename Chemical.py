class Chemical():
    smiles: str
    iupac: str
    nickname: str

    def __init__(self, smiles: str, iupac: str, nickname: str):
        self.smiles = smiles
        self.iupac = iupac
        self.nickname = nickname

    def __init__(self, smiles: str):
        self.smiles = smiles
        self.iupac = get_iupac_from_smiles(smiles)
        self.nickname = get_iupac_from_smiles(smiles)
    
    def to_dict(self):
        return {
            "smiles": self.smiles,
            "iupac": self.iupac,
            "nickname": self.nickname
        }
    
    def to_str(self):
        return f"{{'smiles': '{self.smiles}', 'iupac': '{self.iupac}', 'nickname': '{self.nickname}'}}"
    
def get_iupac_from_smiles(smiles: str) -> str:
    return "iupac"  # placeholder

STR_START_CHEMS = ";".join(
    Chemical(i).to_str() for i in ["[Ca++].[O-]C([O-])=O", "O=O", "CC(=O)O", "O"]
)