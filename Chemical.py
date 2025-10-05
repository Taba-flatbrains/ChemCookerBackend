class Chemical():
    smile: str
    iupac: str
    nickname: str

    def __init__(self, smile: str, iupac: str, nickname: str):
        self.smile = smile
        self.iupac = iupac
        self.nickname = nickname

    def __init__(self, smile: str):
        self.smile = smile
        self.iupac = get_iupac_from_smile(smile)
        self.nickname = get_iupac_from_smile(smile)
    
    def to_dict(self):
        return {
            "smile": self.smile,
            "iupac": self.iupac,
            "nickname": self.nickname
        }
    
    def to_str(self):
        return f"{{'smile': '{self.smile}', 'iupac': '{self.iupac}', 'nickname': '{self.nickname}'}}"
    
def get_iupac_from_smile(smile: str) -> str:
    return "iupac"  # placeholder

# todo: check if chemicals are the same (there are many ways to display one chemical as a smile)

STR_START_CHEMS = ";".join(
    Chemical(i).smile for i in ["[Ca++].[O-]C([O-])=O", "O=O", "CC(=O)O", "O"]
)