from abc import ABC
from dataclasses import dataclass
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

# not really an ast node...
class ASTUninitValue(ASTNode):
    ...

class ASTInferType(ASTNode):
    ...

class ASTNoReturn(ASTNode):
    ...

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
        return cls((lvalue, rvalue))

class ASTType(ASTNullary):
    ...

class ASTReturnType(ASTType):
    ...

@dataclass
class ASTTypedIdent(ASTNode):
    ident: ASTIdentifier
    ident_type: ASTType
    @classmethod
    def from_tree(cls, children):
        ident, ident_type = children
        return cls(ident, ident_type)

@dataclass
class ASTFunctionType(ASTType):
    arguments_type: Tuple[ASTType]
    return_type: ASTType | ASTNoReturn

    @classmethod
    def from_tree(cls, children):
        if not children:
            return cls(arguments_type=tuple(), return_type=ASTNoReturn(None))

        if isinstance(children[-1], ASTReturnType):
            *args, return_type = children
        else:
            args = children
            return_type = ASTNoReturn(None)

        return cls(tuple(args), return_type)


class ASTStructureType(ASTType):
    fields: Tuple[ASTTypedIdent]
    @classmethod
    def from_tree(cls, children):
        return cls(tuple(children))


# kinda weird to have this node that should never existin in the final AST
class ASTVarDeclarationAndAssignment(ASTNode):
    @classmethod
    def from_tree(cls, children):
        lvalue, *var_type, rvalue = children
        if var_type:
            var_type, = var_type
        else:
            var_type = ASTInferType(None)
        return cls((lvalue, var_type, rvalue))


@dataclass
class ASTVarDeclaration(ASTNode):
    ident: ASTIdentifier
    var_type: ASTIdentifier | ASTType
    value: ASTExpression | ASTUninitValue
    @classmethod
    def from_tree(cls, children):
        if isinstance(children[0], ASTVarDeclarationAndAssignment):
            child, = children
            return cls(*child.value)

        lvalue, var_type = children
        rvalue = ASTUninitValue(None)
        return cls(lvalue, var_type, rvalue)

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
class ASTWhileStatement(ASTNode):
    cond: ASTExpression
    block: ASTBlock
    @classmethod
    def from_tree(cls, children):
        cond, block = children
        return cls(cond, block)

@dataclass
class ASTFunctionDeclare(ASTNode):
    arguments: Tuple[ASTTypedIdent]
    return_type: ASTIdentifier | ASTNoReturn
    body: ASTBlock

    # runtime attribute
    jit_function_call: Callable | None = None
    @classmethod
    def from_tree(cls, children):
        *typed_args_and_return, body = children

        if typed_args_and_return and isinstance(typed_args_and_return[-1], ASTReturnType):
            *typed_args, return_type = typed_args_and_return
        else:
            return_type = ASTNoReturn(None)
            typed_args = typed_args_and_return

        return cls(tuple(typed_args), return_type, body)


@dataclass
class ASTFunctionCall(ASTNode):
    func_name: str
    arguments: Tuple[ASTExpression]
    @classmethod
    def from_tree(cls, children):
        func_name, *args = children
        return cls(func_name, tuple(args))


@dataclass
class ASTStructMember(ASTNode):
    name: ASTIdentifier
    value: "ASTExpression | ASTNumber | ASTStructValue"
    @classmethod
    def from_tree(cls, children):
        name, value = children
        return cls(name, value)

@dataclass
class ASTStructValue(ASTNode):
    fields: Tuple[ASTStructMember]
    @classmethod
    def from_tree(cls, children):
        # TODO: check that there are no duplicates field names
        return cls(tuple(children))


@dataclass
class ASTFieldLookup(ASTNode):
    obj: ASTIdentifier
    field: ASTIdentifier
    @classmethod
    def from_tree(cls, children):
        obj, field = children
        return cls(obj, field)

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
    while_statement = ASTWhileStatement.from_tree
    var_declaration = ASTVarDeclaration.from_tree
    var_declaration_and_assignement = ASTVarDeclarationAndAssignment.from_tree
    var_assignment = ASTAssignment.from_tree

    typed_ident = ASTTypedIdent.from_tree
    function_type = ASTFunctionType.from_tree
    struct_type = ASTStructureType.from_tree
    
    struct_member = ASTStructMember.from_tree
    struct_value = ASTStructValue.from_tree
    field_lookup = ASTFieldLookup.from_tree

    expression = ASTExpression.from_tree
    typ = ASTType.from_tree
    ret_typ = ASTReturnType.from_tree
    identifier = ASTIdentifier.from_tree
    number = ASTNumber.from_tree
    prec_1 = ASTBinaryOp.from_tree
    prec_2 = ASTBinaryOp.from_tree
    prec_3 = ASTBinaryOp.from_tree


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
