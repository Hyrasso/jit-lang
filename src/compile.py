from typing import Any
from ast_definition import *
import ctypes
from ctypes import CDLL
from enum import Enum
from pathlib import Path
import subprocess
from textwrap import indent

from utils import Environment
from ast_definition import ASTFunctionDeclare

class JITValuError(ValueError):...

class Register(Enum):
    RAX = "rax"
    RDI = "rdi"
    RSI = "rsi"
    RDX = "rdx"
    RCX = "rcx"
    R8 = "r8"
    R9 = "r9"

class StackOffset(int):...

CALL_ORDER = [Register.RDI, Register.RSI, Register.RDX, Register.RCX, Register.R8 , Register.R9]

def systemv_call_order(sizes):
    for size, reg in zip(sizes, CALL_ORDER):
        assert size <= 8
        yield reg
    for idx, size in enumerate(sizes[6:]):
        assert size <= 8
        yield StackOffset(idx * 8)


BINARY_OP_FUNC_PATTERN = """
{label}:
    # enter
    pushq %rbp
    movq %rsp, %rbp

    movq %rdi, %rax
    {op} %rsi, %rax

    # leave
    movq %rbp, %rsp
    popq %rbp
    retq
"""

FACTOR_FUNC_PATTERN = """
{label}:
    # enter
    pushq %rbp
    movq %rsp, %rbp

    xorq %rdx, %rdx # for division as it uses rdx:rax as input
    movq %rdi, %rax
    {op} %rsi

    # leave
    movq %rbp, %rsp
    popq %rbp
    retq
"""

ADD_FUNC = BINARY_OP_FUNC_PATTERN.format(label="add", op="addq")
SUB_FUNC = BINARY_OP_FUNC_PATTERN.format(label="sub", op="subq")

MUL_FUNC = FACTOR_FUNC_PATTERN.format(label="mul", op="mulq")
DIV_FUNC = FACTOR_FUNC_PATTERN.format(label="div", op="divq")

def to_c_type(arg):
    match arg:
        case ASTNumber(val):
            return ctypes.c_int64(val)
        case a:
            raise NotImplementedError(f"Conversion to ctypes not implemented for {a}")

class JITFunctionCall:
    def __init__(self, function_label, function_args, jit_engine) -> None:
        self.jit_engine = jit_engine
        self.function_args = function_args
        self.function_label = function_label
    
    def __call__(self, *args) -> Any:
        assert len(args) == len(self.function_args)
        compiled_func = self.jit_engine.jitted_lib[f"{self.function_label}"]
        compiled_func.argtypes = [ctypes.c_int64] * len(self.function_args)
        compiled_func.restype = ctypes.c_int64

        ctype_args = [to_c_type(arg) for arg in args]
        res = compiled_func(*ctype_args)

        return ASTNumber(res)


class JITEngine:
    asm_file_name = "jitted_functions.s"
    def __init__(self, compilation_dir) -> None:
        self.compilation_dir = Path(compilation_dir)
        self.compilation_dir.mkdir(parents=True, exist_ok=True)

        self._compiled_functions = [
            ADD_FUNC,
            SUB_FUNC,
            MUL_FUNC,
            DIV_FUNC,
        ]

        self.jitted_lib: CDLL = CDLL(None)

        # load dlclose from stdlib
        self._dl_close_func = ctypes.CDLL("").dlclose
        self._dl_close_func.argtypes = [ctypes.c_void_p]
    
    def compile_function(self, func: ASTFunctionDeclare, env):
        # generate assembler

        compiled_function_label = f"func_{len(self._compiled_functions) + 1}"

        ctx = CompilationContext(block_label=compiled_function_label, export_func=True)

        compile_function(func, env, ctx)

        self._compiled_functions.append(str(ctx))

        func_args = func.arguments
        compiled_func = JITFunctionCall(compiled_function_label, func_args, self)
        func.jit_function_call = compiled_func

        self.reload()


    
    def reload(self):
        asm_code = "\n\n".join(self._compiled_functions) + "\n"

        target_file = self.compilation_dir / self.asm_file_name

        target_file.write_text(asm_code)

        target_lib = target_file.with_suffix('.so')

        res = subprocess.run(["gcc", "-shared", "-g", "-o", f"{target_lib}", f"{target_file}"], capture_output=True)
        if res.returncode != 0:
            raise RuntimeError(f"Failed to jit compile with error: {res.stderr}")

        self._dl_close_func(self.jitted_lib._handle)

        self.jitted_lib = CDLL(str(target_lib))




def _source_to_str(source) -> str:
    match source:
        case ASTNumber(val):
            # tofix: assume all values are int 64
            assert val < 2**64 and val > -2**63, val
            source = f"${val}"
        case Register() as reg:
            source = f"%{reg.value}"
        case StackOffset(offset):
            # at 0 overwrites the previous rbp
            source = f"{offset}(%rbp)"
        case int():
            raise RuntimeError("Unexpectd int")
        case _:
            raise NotImplementedError(f"Unsupported move origin {source}")

    return source


def _format_comment(comment) -> str:
    if comment is None:
        return ""

    return f" # {comment}"


class CompilationContext:
    def __init__(self, block_label, stack_size=0, export_func=False) -> None:
        self.block_label = block_label
        self.block = []
        self.export_func = export_func
        self.stack_size = stack_size # size allocated on the stack
    
    def __str__(self) -> str:
        res = f"{self.block_label}:\n" + indent("\n".join(self.block), prefix="    ")
        if self.export_func:
            res = f".global {self.block_label}\n.type {self.block_label}, @function\n{res}\n"
        return res
    
    
    def emit_move(self, source, destination, comment=None):

        if isinstance(source, StackOffset) and isinstance(destination, StackOffset): 
            raise NotImplementedError("stack to stack move not implemented yet")
        destination = _source_to_str(destination)
        
        source = _source_to_str(source)
            

        self.block.append(
            f"movq {source}, {destination}{_format_comment(comment)}"
        )


    def emit_push(self, source, comment=None):
        source = _source_to_str(source)
        self.block.append(f"pushq {source}")
    
    def emit_call(self, target):
        assert isinstance(target, str)
        self.block.append(f"callq {target}")
    
    def emit_prelude(self):
        # TODO: caller/callee reg saved stuff
        self.block.extend([
            "# enter",
            "pushq %rbp",
            "movq %rsp, %rbp",
        ])

    def emit_epilogue(self):
        # TODO: caller/callee reg saved stuff
        self.block.extend([
            "# leave",
            "movq %rbp, %rsp",
            "popq %rbp",
            "retq"
        ])
    
    def emit_grow_stack(self, size):
        assert size % 8 == 0
        self.stack_size += size
        self.block.append(f"subq ${size}, %rsp")

    def emit_shrink_stack(self, size):
        assert size % 8 == 0
        self.stack_size -= size
        self.block.append(f"addq ${size}, %rsp")



def compile_function(func: ASTFunctionDeclare, env, compilation_context: CompilationContext, inline=False):
    compilation_context.emit_prelude()

    # move arguments to the expected places
    compilation_context.emit_grow_stack(8 * len(func.arguments))
    current_size = compilation_context.stack_size
    func_env = {}
    for idx, (addr, arg) in enumerate(zip(systemv_call_order([8] * len(func.arguments)), func.arguments)):
        dest = StackOffset(-(current_size - idx * 8))
        compilation_context.emit_move(source=addr, destination=dest)
        func_env[arg] = dest


    # set arguments
    func_env = Environment(parent=env, env=func_env)
    compile_block(func.body, func_env, compilation_context)

    compilation_context.emit_epilogue()


def compile_block(block, env, compilation_context):
    for statement in block.value:
        compile_statement(statement, env, compilation_context)

def compile_statement(stmt, env, compilation_context):
    match stmt.value:
        case ASTExpression(value):
            compile_expression(value, env, compilation_context)
        case ASTAssignment((lvalue, rvalue)):
            rvalue = compile_assignement(lvalue, rvalue, env, compilation_context)
        case ASTNamedBlock():
            raise NotImplementedError(f"Interpret statement not implemented for named blocks")
        case ASTIfStatement():
            # compile each block seperatly with its own label
            # compile expression and test result
            #   ...
            #   <compile cond>
            #   test %rax, %rax
            #   jz if_branch
            #   jmp else_branch
            # if_branch:
            #   ...
            #   jmp end_if
            # else_branch:
            #   ...
            #   jmp end_if
            # else_branch:
            #   ...
            #   

            # generate 'prelude' and 'epilogue'
            raise NotImplementedError(f"Interpret statement not implemented for named blocks")
        case v:
            raise NotImplementedError(f"Interpret statement not implemented for {v}")

def compile_expression(exp, env, compilation_context: CompilationContext):
    # kinda inline function call
    match exp:
        case ASTNumber() as val:
            # move literal to rax
            compilation_context.emit_move(source=val, destination=Register.RAX)
        case ASTIdentifier(ident):
            # retrieve value and move it to rax
            arg = env.get(ident)
            compilation_context.emit_move(source=arg, destination=Register.RAX)
        case ASTBinaryOp(a, op, b):
            # raise NotImplementedError("Binary operation not implemented yet")
            assert isinstance(op, ASTOp), type(op)

            # TODO: resolve op to a function then compile like a function call of the operator
            match op.value:
                case "+":
                    compile_function_call("add", (a, b), env, compilation_context)
                case "-":
                    compile_function_call("sub", (a, b), env, compilation_context)
                case "*":
                    compile_function_call("mul", (a, b), env, compilation_context)
                case "/":
                    compile_function_call("div", (a, b), env, compilation_context)
                case o:
                    raise NotImplementedError(f"Operation compilation not implemented for {o}")
        case ASTFunctionDeclare(_):
            raise NotImplementedError("Function declaration inside expression is not supported yet")
        case ASTFunctionCall(func_name, arguments):
            func = env.get(func_name)
            compile_function_call(func, arguments, env, compilation_context)

def compile_assignement(lvalue, rvalue, env: Environment, compilation_context: CompilationContext):
    if not isinstance(lvalue, ASTIdentifier):
        raise NotImplementedError(f"Assigning to anything else than an identifier is not supported yet (found: {type(lvalue)})")
    match rvalue:
        case ASTFunctionDeclare() as func_dec:
            # update env/compilation context to be able to call the function later
            raise NotImplementedError("Function declare compilation is not implemented yet")
            # should be called from jit engine
            compile_function(func_dec, env, compilation_context)
        case ASTExpression(exp):
            # add some space on the stack for the new variable
            compilation_context.emit_grow_stack(8)
            var_addr = StackOffset(-compilation_context.stack_size)
            env.set(lvalue.value, var_addr)
            compile_expression(exp, env, compilation_context)
            compilation_context.emit_move(source=Register.RAX, destination=var_addr)

def compile_function_call(func, arguments, env: Environment, compilation_context: CompilationContext):
    if isinstance(func, str):
        func_label = func
    else:
        raise NotImplementedError("Calling non builtin functions not implemented yet")

    # assume all values are 64 bits, todo compute stack size needed
    # compilation_context.emit_reserve_stack(len(args))
    # tofix: stack arguments
    if len(arguments) > 6:
        compilation_context.emit_grow_stack(8 * len(arguments))
    current_size = compilation_context.stack_size
    for addr, arg in zip(systemv_call_order([8] * len(arguments)), arguments):
        # TODO: compile expression should accept a target destination for the result to be stored in, for now assumes its in rax
        compile_expression(arg, env, compilation_context)
        # compilation_context.emit_push(source=Register.RAX)
        if isinstance(addr, StackOffset):
            # adjust stack offset from the point of view of the caller
            addr = StackOffset(current_size - addr)
        compilation_context.emit_move(source=Register.RAX, destination=addr)
    compilation_context.emit_call(func_label)
    if len(arguments) > 6:
        compilation_context.emit_shrink_stack(8 * len(arguments))
