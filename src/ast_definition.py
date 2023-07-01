from abc import ABC
from dataclasses import dataclass, field
from typing import Callable, Tuple

import lark
from lark.indenter import Indenter

class ASTNode(ABC):
    __match_args__ = ("value",)
    @classmethod
    def from_tree(cls, children):
        return cls(children)

    def __init__(self, value) -> None:
        self.value = value
    
    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        return f"{cls_name}({repr(self.value) if self.value is not None else ''})"

# Terminals
class ASTNumber(ASTNode):
    @classmethod
    def from_tree(cls, children):
        val, = children
        return cls(int(val))
    
    def __eq__(self, other: "ASTNumber") -> bool:
        if not isinstance(other, ASTNumber):
            return False
        return other.value == self.value

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
        return f"{cls_name}({self.a!r}, {self.op!r}, {self.b!r})"

    @classmethod
    def from_tree(cls, children):
        assert len(children) > 2 and len(children) % 2 == 1, len(children)
        a, op, b, *rest = children
        res = cls(a, ASTOp(str(op)), b)
        while rest:
            op, b, *rest = rest
            res = ASTBinaryOp(res, ASTOp(str(op)), b)
        return res

class ASTExpression(ASTNullary):...
class ASTStatement(ASTNullary):...


class ASTAssignment(ASTNode):
    @classmethod
    def from_tree(cls, children):
        lvalue,  rvalue = children
        return cls((ASTIdentifier(str(lvalue)), rvalue))

class ASTModule(ASTNullary):...

class ASTBlock(ASTNode):
    value: Tuple[ASTStatement]
    @classmethod
    def from_tree(cls, children):
        assert all(isinstance(st, ASTStatement) for st in children)
        statements = [statement for statement in children if isinstance(statement, ASTStatement)]
        return cls(tuple(statements))

class ASTNamedBlock(ASTNode):
    __match_args__ = ("name", "block")
    def __init__(self, name, block) -> None:
        self.name = name
        self.block = block
    @classmethod
    def from_tree(cls, children):
        name, block = children
        return cls(str(name), block)
    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        return f"{cls_name}({self.name!r}, {self.block!r})"

@dataclass
class ASTIfStatement(ASTNode):
    cond: ASTExpression
    if_block: ASTBlock
    else_block: ASTBlock | None
    @classmethod
    def from_tree(cls, children):
        cond, if_block, *else_block = children
        return cls(cond, if_block, else_block[0] if else_block else None)

@dataclass
class ASTFunctionDeclare(ASTNode):
    arguments: Tuple[str]
    body: ASTBlock

    # runtime attribute
    jit_function_call: Callable | None = None
    @classmethod
    def from_tree(cls, children):
        *args, body = children
        return cls(tuple(map(str, args)), body)

def inline_function_to_function_declare(children, *args):
    print(children, args)

@dataclass
class ASTFunctionCall(ASTNode):
    func_name: str
    arguments: Tuple[ASTExpression]
    @classmethod
    def from_tree(cls, children):
        func_name, *args = children
        return cls(str(func_name), tuple(args))

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
    block = ASTBlock.from_tree
    named_block = ASTNamedBlock.from_tree
    func_declare = ASTFunctionDeclare.from_tree
    @staticmethod
    def inline_func_declare(children):
        *args, expression = children
        return ASTFunctionDeclare.from_tree([*args, ASTBlock((ASTStatement(expression),))])
    func_call = ASTFunctionCall.from_tree
    statement = ASTStatement.from_tree
    if_statement = ASTIfStatement.from_tree
    assignment = ASTAssignment.from_tree
    expression = ASTExpression.from_tree
    identifier = ASTIdentifier.from_tree
    number = ASTNumber.from_tree
    prec_1 = ASTBinaryOp.from_tree
    prec_2 = ASTBinaryOp.from_tree


class BlockIndenter(Indenter):
    @property
    def NL_type(self):
        return "_NEW_LINE"
    @property
    def OPEN_PAREN_types(self):
        return []
    @property
    def CLOSE_PAREN_types(self):
        return  []
    @property
    def INDENT_type(self):
        return  "_INDENT"
    @property
    def DEDENT_type(self):
        return  "_DEDENT"
    @property
    def tab_len(self):
        return 8
