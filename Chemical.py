class Chemical():
    smile: str
    iupac: str
    nickname: str

    def __init__(self, smile: str, iupac: str = "", nickname: str = ""):
        self.smile = smile
        self.iupac = iupac
        self.nickname = nickname
    
    def to_dict(self):
        return {
            "smile": self.smile,
            "iupac": self.iupac,
            "nickname": self.nickname
        }
    
    def to_str(self):
        return f"{{'smile': '{self.smile}', 'iupac': '{self.iupac}', 'nickname': '{self.nickname}'}}"

STR_START_CHEMS = ";".join(
    Chemical(i).smile for i in ["[Ca+2].[O-]C([O-])=O", "O=O", "CC(=O)O", "O"]
)