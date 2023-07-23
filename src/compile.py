from typing import Any
from ast_definition import *
from collections import Counter
import ctypes
from ctypes import CDLL
from enum import Enum
from pathlib import Path
import subprocess
from textwrap import indent

from utils import Environment
from ast_definition import ASTFunctionDeclare
from jit_builtins import BUILTIN_FUNC_ASM
from runtime_values import Number, U64

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


def to_c_type(arg):
    match arg:
        case U64(val):
            return ctypes.c_uint64(val)
        case Number(val):
            return ctypes.c_int64(val)
        case a:
            raise NotImplementedError(f"Conversion to ctypes not implemented for {a}")

class JITFunctionCall:
    def __init__(self, function_label, function_args, function_ret_type, jit_engine) -> None:
        self.jit_engine = jit_engine
        self.function_args = function_args
        self.function_label = function_label
        self.func_ret_type = function_ret_type
    
    def __call__(self, *args) -> Any:
        assert len(args) == len(self.function_args)
        compiled_func = self.jit_engine.jitted_lib[f"{self.function_label}"]
        # TODO: add a typ_to_c_type, and val_to_ctype that does typ_to_c_type(typ(val))(val)
        compiled_func.argtypes = [ctypes.c_int64] * len(self.function_args)
        compiled_func.restype = ctypes.c_int64

        ctype_args = [to_c_type(arg) for arg in args]
        res = compiled_func(*ctype_args)

        return self.func_ret_type(res)


class JITEngine:
    asm_file_name = "jitted_functions.s"
    def __init__(self, compilation_dir) -> None:
        self.compilation_dir = Path(compilation_dir)
        self.compilation_dir.mkdir(parents=True, exist_ok=True)

        self._compiled_functions = [*BUILTIN_FUNC_ASM]

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
        func_ret_type = func.return_type
        compiled_func = JITFunctionCall(compiled_function_label, func_args, func_ret_type, self)
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



class Label:
    def __init__(self, value) -> None:
        self.value = value
    def __str__(self) -> str:
        return f"{self.value}"

class CompilationContext:
    _unique_block_index = Counter()
    def __init__(self, block_label, stack_size=0, export_func=False) -> None:
        self.block_label = block_label
        self.block = []
        self.export_func = export_func
        self.stack_size = stack_size # size allocated on the stack
    
    def __str__(self) -> str:
        res = f"{self.block_label}:\n" + "\n".join([indent(b, prefix="    ") if isinstance(b, str) else str(b) for b in self.block])
        if self.export_func:
            res = f".global {self.block_label}\n.type {self.block_label}, @function\n{res}\n"
        return res
    
    def include_block(self, ctx: "CompilationContext"):
        self.block.append(ctx)
    
    def get_unique_label(self, prefix):
        self._unique_block_index[prefix] += 1
        return f"{prefix}_{self._unique_block_index[prefix]}"

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

    def emit_jump_target(self, target: Label):
        # weird trick to go around auto indent
        assert isinstance(target, Label)
        self.block.append(Label(f"{target.value}:"))

    def emit_jump(self, target: Label):
        assert isinstance(target, Label)
        self.block.append(f"jmp {target}")
    
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
    
    def emit_if_branch(self, cond_true_label, cond_false_label):
        self.block.extend([
            "cmp $0, %rax",
            f"jne {cond_true_label}",
            f"jmp {cond_false_label}",
        ])

    def emit_cond_jump(self, cond_true_label):
        self.block.extend([
            "cmp $0, %rax",
            f"jne {cond_true_label}",
        ])



def compile_function(func: ASTFunctionDeclare, env, compilation_context: CompilationContext, inline=False):
    compilation_context.emit_prelude()

    # move arguments to the expected places
    compilation_context.emit_grow_stack(8 * len(func.arguments))
    current_size = compilation_context.stack_size
    # set arguments
    func_env = Environment(parent=env, env=None)
    for idx, (addr, arg) in enumerate(zip(systemv_call_order([8] * len(func.arguments)), func.arguments)):
        dest = StackOffset(-(current_size - idx * 8))
        compilation_context.emit_move(source=addr, destination=dest)
        func_env.set(arg.ident.value, dest, None)


    compile_block(func.body, func_env, compilation_context)

    compilation_context.emit_epilogue()


def compile_block(block, env, compilation_context):
    for statement in block.value:
        compile_statement(statement, env, compilation_context)

def compile_statement(stmt, env, compilation_context):
    match stmt.value:
        case ASTExpression(value):
            compile_expression(value, env, compilation_context)
        case ASTVarDeclaration(ident, var_type,  rvalue):
            compile_var_declaration(ident, var_type, rvalue, env, compilation_context)
        case ASTAssignment((lvalue, rvalue)):
            if not isinstance(lvalue, ASTIdentifier):
                raise NotImplementedError(f"Compiling assignement to {lvalue} not implemented")
            compile_var_assignement(lvalue, rvalue, env, compilation_context)
        case ASTNamedBlock():
            raise NotImplementedError(f"Interpret statement not implemented for named blocks")
        case ASTIfStatement() as if_stmt:
            compile_if_statement(if_stmt, env, compilation_context)
            # raise NotImplementedError(f"Interpret statement not implemented for if statement")
        case ASTWhileStatement() as while_stmt:
            compile_while_statement(while_stmt, env, compilation_context)
        case v:
            raise NotImplementedError(f"Interpret statement not implemented for {v}")

def compile_if_statement(if_stmt: ASTIfStatement, env: Environment, compilation_context: CompilationContext):

    compile_expression(if_stmt.cond, env, compilation_context)

    cond_true_label = compilation_context.get_unique_label("if_cond_true")
    cond_false_label = compilation_context.get_unique_label("if_cond_false")
    end_if_label = Label(compilation_context.get_unique_label("end_if_label"))

    compilation_context.emit_if_branch(cond_true_label, cond_false_label)

    cond_true_block = CompilationContext(block_label=cond_true_label, stack_size=compilation_context.stack_size)
    cond_true_env = Environment(parent=env)
    compile_block(if_stmt.if_block, cond_true_env, cond_true_block)
    cond_true_block.emit_jump(end_if_label)
    compilation_context.include_block(cond_true_block)

    cond_false_block = CompilationContext(block_label=cond_false_label, stack_size=compilation_context.stack_size)
    if if_stmt.else_block is not None:
        cond_false_env = Environment(parent=env)
        compile_block(if_stmt.else_block, cond_false_env, cond_false_block)
    cond_false_block.emit_jump(end_if_label)
    compilation_context.include_block(cond_false_block)

    compilation_context.emit_jump_target(end_if_label)

def compile_while_statement(while_stmt: ASTWhileStatement, env: Environment, compilation_context: CompilationContext):
    loop_label = compilation_context.get_unique_label("while")
    block_ctx = CompilationContext(block_label=loop_label, stack_size=compilation_context.stack_size)
    compile_block(while_stmt.block, env, block_ctx)
    compile_expression(while_stmt.cond, env, block_ctx)
    block_ctx.emit_cond_jump(loop_label)
    compilation_context.include_block(block_ctx)

def compile_expression(exp, env, compilation_context: CompilationContext):
    # kinda inline function call
    match exp:
        case ASTExpression(exp):
            return compile_expression(exp, env, compilation_context)
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
                case "<":
                    compile_function_call("lt", (a, b), env, compilation_context)
                case ">":
                    compile_function_call("gt", (a, b), env, compilation_context)
                case "<=":
                    compile_function_call("lte", (a, b), env, compilation_context)
                case ">=":
                    compile_function_call("gte", (a, b), env, compilation_context)
                case "==":
                    compile_function_call("eq", (a, b), env, compilation_context)
                case "!=":
                    compile_function_call("neq", (a, b), env, compilation_context)
                case o:
                    raise NotImplementedError(f"Operation compilation not implemented for {o}")
        case ASTFunctionDeclare(_):
            raise NotImplementedError("Function declaration inside expression is not supported yet")
        case ASTFunctionCall(func_name, arguments):
            func = env.get(func_name)
            compile_function_call(func, arguments, env, compilation_context)
        case o:
            raise NotImplementedError(f"Compilation of {type(o)} not implemented yet")

def compile_var_declaration(lvalue, var_type, rvalue, env: Environment, compilation_context: CompilationContext):
    if not isinstance(var_type.value, ASTIdentifier) and not var_type.value.value == "int":
        raise NotImplementedError(f"Compiling variablle declaration of type {var_type.value} is not implemented")
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
            env.set(lvalue.value, var_addr, None) # TODO: do not ignore type
            compile_expression(exp, env, compilation_context)
            compilation_context.emit_move(source=Register.RAX, destination=var_addr)

def compile_var_assignement(lvalue, rvalue, env, compilation_context: CompilationContext):
    match rvalue:
        case ASTExpression(exp):
            if not isinstance(lvalue, ASTIdentifier):
                raise NotImplementedError(f"Compiling assignement to {exp} not implemented")
            var_addr = env.get(lvalue.value)
            # TODO: check that types of value and variable match
            compile_expression(exp, env, compilation_context)
            compilation_context.emit_move(source=Register.RAX, destination=var_addr)
        case o:
            raise NotImplementedError(f"Compiling assigning {o} not implemented")

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
