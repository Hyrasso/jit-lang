from typing import Callable
from ast_definition import *

Ident = str

class Number:
    def __init__(self, value) -> None:
        self.value = int(value)
    
    def __str__(self):
        return str(self.value)

class Function:
    def __init__(self, arguments, code) -> None:
        self.arguments = arguments
        assert isinstance(code, ASTBlock), type(code)
        self.code = code

class Environment:
    def __init__(self, parent=None, env=None) -> None:
        self.parent = parent
        self._env = env if env is not None else {}

    def get(self, val):
        if val in self._env:
            return self._env[val]
        
        if self.parent is not None:
            return self.parent.get(val)
        
        raise RuntimeError(f"Unknown {val} in env")
    
    # systematicaly shadow parent env
    def set(self, var, val):
        self._env[var] = val


BUILTIN_FUNCTIONS = {
    "/": lambda a, b: Number(a.value / b.value),
    "*": lambda a, b: Number(a.value * b.value),
    "+": lambda a, b: Number(a.value + b.value),
    "-": lambda a, b: Number(a.value - b.value),
    "print": lambda *a: print(*a)
}

def run(ast):

    # TODO: initalize environment
    builtin_env = Environment(parent=None, env=BUILTIN_FUNCTIONS)
    
    if isinstance(ast, ASTModule):
        interpret_module(ast, builtin_env)
    else:
        raise ValueError(f"Expecting an ASTModule, got {type(ast)}")

def interpret_module(node: ASTModule, env: Environment):
    interpret_block(node.value, env)

def interpret_block(node: ASTBlock, env: Environment):
    for statement in node.value:
        res = interpret_statement(statement, env)
    return res

def interpret_statement(node: ASTStatement, env: Environment):
    match node.value:
        case ASTExpression(value):
            return interpret_expression(value, env)
        case ASTAssignment((lvalue, rvalue)):
            rvalue = interpret_expression(rvalue, env)
            env.set(lvalue.value, rvalue)
            return
        case ASTNamedBlock(block_name, block):
            return interpret_block(block, env)
        case v:
            raise NotImplementedError(f"Interpret statement not implemented for {v}")


def interpret_expression(node: ASTExpression | ASTNumber | ASTBinaryOp, env: Environment):
    match node:
        case ASTNumber(val):
            return Number(val)
        case ASTIdentifier(ident):
            return env.get(ident)
        case Ident(ident):
            return env.get(ident)
        case ASTBinaryOp(a, op, b):
            val_a = interpret_expression(a, env)
            val_b = interpret_expression(b, env)
            val_op = op.value
            op_func = env.get(val_op)
            return interpret_func_call(op_func, (val_a, val_b), env)
        case ASTInlineFunctionDeclare(arguments, body):
            return Function(arguments, code=body)
        case ASTFunctionDeclare(arguments, body):
            return Function(arguments, code=body)
        case ASTFunctionCall(func_name, arguments):
            arg_values = [interpret_expression(arg, env) for arg in arguments]
            func = env.get(func_name)
            return interpret_func_call(func, arg_values, env)

    
    if not isinstance(node, ASTExpression):
        raise ValueError(f"Unexpected expression {type(node)}")

    return interpret_expression(node.value, env)

def interpret_func_call(func: Function | Callable, arguments, env: Environment):
    if callable(func):
        return func(*arguments)

    assert isinstance(func, Function), type(func)

    if len(func.arguments) != len(arguments):
        raise RuntimeError(f"Wrong number of arguments, got {len(arguments)}, expected {len(func.arguments)}")
    new_env = Environment(parent=env, env=dict(zip(func.arguments, arguments)))
    return interpret_block(func.code, new_env)


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    from lark_parser import initialize_parser

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--input-file", type=Path, required=True)
    arg_parser.add_argument("--grammar-definition", default=Path(__file__).absolute().parent / "grammar.lark")
    args = arg_parser.parse_args()

    parser, ast_builder = initialize_parser(args.grammar_definition)

    res = parser.parse(Path(args.input_file).read_text())

    run(res)