from abc import ABC
from typing import Tuple

import lark

class ASTNode(ABC):
    __match_args__ = ("value",)
    @classmethod
    def from_tree(cls, children):
        return cls(children)

    def __init__(self, value) -> None:
        self.value = value
    
    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        return f"{cls_name}({self.value if self.value is not None else ''})"

# Terminals
class ASTNumber(ASTNode):
    @classmethod
    def from_tree(cls, children):
        val, = children
        return cls(int(val))

class ASTOp(ASTNode):...
class ASTIdentifier(ASTNode):
    @classmethod
    def from_tree(cls, children):
        val, = children
        return cls(str(val))

# rules
class ASTNullary(ASTNode):
    @classmethod
    def from_tree(cls, children):
        elem, = children
        return cls(elem)

class ASTBinaryOp(ASTNode):
    __match_args__ = ("a", "op", "b")
    def __init__(self, a, op, b) -> None:
        self.a = a
        self.op = op
        self.b = b
    
    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        return f"{cls_name}({self.a}, {self.op}, {self.b})"

    @classmethod
    def from_tree(cls, children):
        a, op, b = children
        return cls(a, ASTOp(str(op)), b)

class ASTExpression(ASTNullary):...
class ASTStatement(ASTNullary):...

class ASTAssignment(ASTNode):
    @classmethod
    def from_tree(cls, children):
        lvalue,  rvalue = children
        return cls((ASTIdentifier(str(lvalue)), rvalue))

class ASTModule(ASTNode):
    value: Tuple[ASTStatement]
    @classmethod
    def from_tree(cls, children):
        statements = [statement for statement in children if isinstance(statement, ASTStatement)]
        return cls(tuple(statements))
    

class ASTBuilder(lark.Transformer):
    def __init__(self, visit_tokens: bool = True) -> None:
        super().__init__(visit_tokens)
        self.comments = []
    
    def collect_comment(self, token: lark.Token):
        self.comments.append(token)
        return token
    
    def lexer_callbacks(self):
        return {
            "COMMENT": self.collect_comment
        }

    module = ASTModule.from_tree
    statement = ASTStatement.from_tree
    assignment = ASTAssignment.from_tree
    expression = ASTExpression.from_tree
    identifier = ASTIdentifier.from_tree
    number = ASTNumber.from_tree
    prec_1 = ASTBinaryOp.from_tree
    prec_2 = ASTBinaryOp.from_tree