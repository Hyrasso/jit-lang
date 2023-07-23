from ast_definition import ASTNumber, ASTStructValue, ASTStructureType, ASTTypedIdent

class Number:
    __match_args__ = ("value",)
    def __init__(self, value) -> None:
        if isinstance(value, (Number, ASTNumber)):
            value = value.value
        elif isinstance(value, int):
            ...
        else:
            raise ValueError(f"Unexpected value {value} for type {type(self)}")
        self.value = value
    
    @classmethod
    def cast(cls, obj):
        return cls(obj)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.value!r})"
    
    def __eq__(self, other) -> bool:
        # unsure about the effects of removing a strict type equality and using number subtype, or .value directly
        if type(self) != type(other):
            return False
        return self.value == other.value
        

class U64(Number):
    def __init__(self, value) -> None:
        super().__init__(value)
        self.value = int(self.value) % 2**64
    

class Struct:
    @staticmethod
    def cast(obj):
        if not isinstance(obj, ASTStructValue):
            raise TypeError(f"Unexpected obj of type {obj}, expecting a structure")
        
        return ASTStructureType(
            tuple(ASTTypedIdent(f.ident, f.value) for f in obj.fields)
        )