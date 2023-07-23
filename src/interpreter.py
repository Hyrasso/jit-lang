import time
from typing import Callable
from ast_definition import *

import logging

from compile import JITEngine, JITValuError
from utils import Environment, TypedVar
from runtime_values import *

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)

JIT_COMPILE = True
SHADOW_JIT = True
DEBUG = False


# TODO: add type checking to builtin functions
BUILTIN_FUNCTIONS = {
    "/":  TypedVar(lambda a, b: type(a)(a.value / b.value), ASTInferType(None)),
    "*":  TypedVar(lambda a, b: type(a)(a.value * b.value), ASTInferType(None)),
    "+":  TypedVar(lambda a, b: type(a)(a.value + b.value), ASTInferType(None)),
    "-":  TypedVar(lambda a, b: type(a)(a.value - b.value), ASTInferType(None)),
    "<":  TypedVar(lambda a, b: type(a)(int(a.value < b.value)), ASTInferType(None)),
    "<=": TypedVar(lambda a, b: type(a)(int(a.value <= b.value)), ASTInferType(None)),
    ">":  TypedVar(lambda a, b: type(a)(int(a.value > b.value)), ASTInferType(None)),
    ">=": TypedVar(lambda a, b: type(a)(int(a.value >= b.value)), ASTInferType(None)),
    "==":  TypedVar(lambda a, b: type(a)(int(a.value == b.value)), ASTInferType(None)),
    "!=":  TypedVar(lambda a, b: type(a)(int(a.value != b.value)), ASTInferType(None)),
    "print": TypedVar(lambda *a: print(*a), ASTInferType(None)),
}

BUILTIN_TYPES = {
    "u64": TypedVar(U64, ASTInferType),
    "struct": TypedVar(Struct, ASTInferType)
}

def run(ast):

    # TODO: initalize environment
    builtin_env = Environment(parent=None, env={**BUILTIN_FUNCTIONS, **BUILTIN_TYPES})
    
    if isinstance(ast, ASTModule):
        interpret_module(ast, builtin_env)
    else:
        raise ValueError(f"Expecting an ASTModule, got {type(ast)}")

def interpret_module(node: ASTModule, env: Environment):
    interpret_block(node.value, env)

def interpret_block(node: ASTBlock, env: Environment) -> ASTNumber | ASTStructValue | ASTNoReturn:
    if len(node.value) == 0:
        raise ValueError("Unexpected empty block")
    res = ASTNoReturn(None)
    for statement in node.value:
        res = interpret_statement(statement, env)
    return res

def interpret_statement(node: ASTStatement, env: Environment) -> ASTNumber | ASTStructValue | ASTNoReturn:
    match node.value:
        case ASTExpression(value):
            return interpret_expression(value, env)
        case ASTAssignment((lvalue, rvalue)):
            assert isinstance(lvalue, ASTIdentifier), type(lvalue)
            var_typ = env.get_typ(lvalue.value)
            rvalue = interpret_expression(rvalue, env)
            rvalue = var_typ.cast(rvalue)
            env.update(lvalue.value, rvalue)
            return ASTNoReturn(None)
        case ASTVarDeclaration(var_name, var_type, rvalue):
            assert isinstance(var_name, ASTIdentifier), type(var_name)
            if isinstance(var_type, ASTInferType):
                raise NotImplementedError("Type inference not implemented yet")
            var_type = interpret_typ(var_type, env)
            if not isinstance(rvalue, ASTUninitValue):
                rvalue = interpret_expression(rvalue, env)
                rvalue = var_type.cast(rvalue)
            env.set(var_name.value, rvalue, var_type)
        # case ASTNamedBlock(block_name, block):
        #     return interpret_block(block, env)
        case ASTIfStatement(cond, true_branch, false_branch):
            cond_res = interpret_expression(cond, env)
            if not isinstance(cond_res, Number):
                raise NotImplementedError(f"If condition only implemented for number values, not {type(cond_res)}")
            block_env = Environment(parent=env)
            if cond_res.value != 0:
                return interpret_block(true_branch, block_env)

            if false_branch is not None:
                return interpret_block(false_branch, block_env)
        case ASTWhileStatement(cond, block):
            cond_res = interpret_expression(cond, env)
            if not isinstance(cond_res, Number):
                raise NotImplementedError(f"While condition should resolve to a number, not {cond_res}")
            while cond_res.value != 0:
                interpret_block(block, env)
                cond_res = interpret_expression(cond, env)
            return ASTNoReturn(None)
        case v:
            raise NotImplementedError(f"Interpret statement not implemented for {v}")
    return ASTNoReturn(None)


def interpret_typ(node, env: Environment):
    match node:
        case ASTUninitValue(_):
            return node
        case ASTNoReturn(_):
            return node
        case ASTIdentifier(ident):
            return env.get(ident)
        case Number(_):
            return node
        case ASTStructureType(fields):
            interp_fields = []
            for field in fields:
                field_typ = interpret_typ(field.ident_type, env)
                interp_fields.append(ASTTypedIdent(field.ident, field_typ))
            
            return ASTStructureType(tuple(interp_fields))

        case ASTType(typ):
            return interpret_typ(typ, env)
        case ASTFunctionType(arg_types, ret_type):
            arguments = []
            for arg in arg_types:
                arguments.append(interpret_typ(arg, env))
            ret = interpret_typ(ret_type, env)

            return ASTFunctionType(tuple(arguments), ret)
        case _:
            raise NotImplementedError(f"Interp of type {node} not implemented")
        

def interpret_expression(node: ASTExpression | ASTNumber | ASTBinaryOp, env: Environment) -> Number | ASTStructValue | ASTFunctionDeclare | ASTNoReturn:
    match node:
        case ASTNumber(val):
            return Number(val)
        case ASTIdentifier(ident):
            return env.get(ident)
        case ASTBinaryOp(a, op, b):
            val_a = interpret_expression(a, env)
            val_b = interpret_expression(b, env)
            val_op = op.value
            op_func = env.get(val_op)
            f_ret = interpret_func_call(op_func, (val_a, val_b), env)
            if isinstance(f_ret, ASTNoReturn):
                raise NotImplementedError()
            return f_ret
        case ASTFunctionDeclare(arguments, ret_typ, body):
            interp_args = []
            for arg in arguments:
                ident_typ = interpret_typ(arg.ident_type, env)
                interp_args.append(ASTTypedIdent(arg.ident, ident_typ))
            
            interp_return_typ = interpret_typ(ret_typ, env)
        
            # TODO: when astnodes and interpreter values are differnt replace with the internal function value
            return ASTFunctionDeclare(tuple(interp_args), interp_return_typ, body)
    
        case ASTFunctionCall(func_name, arguments):
            arg_values = [interpret_expression(arg, env) for arg in arguments]
            func = env.get(func_name.value)
            f_ret = interpret_func_call(func, arg_values, env)
            if f_ret == ASTNoReturn(None):
                return ASTNoReturn(None)
            return f_ret
        case ASTStructValue(fields):
            interp_fields = list()
            for field in fields:
                field_value = interpret_expression(field.value, env)
                interp_fields.append(ASTStructMember(field.ident, field_value))
            return ASTStructValue(tuple(interp_fields))

        case ASTFieldLookup(obj, field_name):
            struct = interpret_expression(obj, env)
            if not isinstance(struct, ASTStructValue):
                raise RuntimeError(f"Attempting to access field of a {type(obj)}, when a struct was expected")
            
            for field in struct.fields:
                if field.ident.value == field_name.value:
                    if isinstance(field.value, ASTExpression):
                        raise ValueError("Unevaluated struct field value")
                    field_value = field.value
                    break
            else:
                raise ValueError(f"Field {field_name} does not exist for struct")
            return field_value

    
    if not isinstance(node, ASTExpression):
        raise ValueError(f"Unexpected expression {type(node)}")

    return interpret_expression(node.value, env)

def interpret_func_call(func: Callable | ASTFunctionDeclare, arguments, env: Environment, force_inteprret=False) -> ASTNumber | ASTStructValue | ASTNoReturn:
    if callable(func):
        return func(*arguments)

    assert isinstance(func, ASTFunctionDeclare), type(func)

    if not force_inteprret and JIT_COMPILE and func.jit_function_call is None:
        try:
            t = time.perf_counter_ns()
            JIT_ENGINE.compile_function(func, env)
            dt = time.perf_counter_ns() - t
            logger.info("Compiled func in %d ns", dt)
        except NotImplementedError as err:
            if DEBUG:
                raise err
            else:
                logger.error(err, exc_info=True)

    if not force_inteprret and func.jit_function_call is not None:
        if SHADOW_JIT:
            t = time.perf_counter_ns()
            interp_res = interpret_func_call(func, arguments, env, force_inteprret=True)
            dt = time.perf_counter_ns() - t
            logger.info("Intepreted func in %d ns", dt)
            try:
                t = time.perf_counter_ns()
                jit_res = func.jit_function_call(*arguments)
                dt = time.perf_counter_ns() - t
                logger.info("Run jitted func in %d ns", dt)
                if interp_res != jit_res:
                    print(f"Jit and interp got different results: jit({jit_res}), interp({interp_res})")
                return jit_res
            except JITValuError:
                logger.info("Failed to call jitted function")
        else:
            try:
                return func.jit_function_call(*arguments)
            except JITValuError:
                logger.info("Failed to call jitted function")

    if len(func.arguments) != len(arguments):
        raise RuntimeError(f"Wrong number of arguments, got {len(arguments)}, expected {len(func.arguments)}")
    new_env = Environment(parent=env)
    for arg_type, call_argument in zip(func.arguments, arguments):
        # TODO: check that the types of the arguments passed to the function match the ones of the function type definition
        call_argument = arg_type.ident_type.cast(call_argument)
        new_env.set(arg_type.ident.value, call_argument, arg_type)
    res = interpret_block(func.body, new_env)
    return func.return_type.cast(res)


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    from lark_parser import initialize_parser

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--input-file", type=Path, required=True)
    arg_parser.add_argument("--grammar-definition", default=Path(__file__).absolute().parent / "grammar.lark")
    arg_parser.add_argument("--jit-compile", action="store_true")

    args = arg_parser.parse_args()

    JIT_COMPILE = args.jit_compile
    JIT_ENGINE = JITEngine(compilation_dir=".jil_cache")

    parser, ast_builder = initialize_parser(args.grammar_definition)

    res = parser.parse(Path(args.input_file).read_text())

    run(res)