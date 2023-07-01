
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

COMP_FUNC_PATTERN = """
{label}:
    # enter
    pushq %rbp
    movq %rsp, %rbp

    xor %rax, %rax
    cmp %rsi, %rdi # rdi - rsi
    {op} %al # signed integers comparison

    # leave
    movq %rbp, %rsp
    popq %rbp
    retq
"""

ADD_FUNC = BINARY_OP_FUNC_PATTERN.format(label="add", op="addq")
SUB_FUNC = BINARY_OP_FUNC_PATTERN.format(label="sub", op="subq")

MUL_FUNC = FACTOR_FUNC_PATTERN.format(label="mul", op="mulq")
DIV_FUNC = FACTOR_FUNC_PATTERN.format(label="div", op="divq")

GT_FUNC = COMP_FUNC_PATTERN.format(label="gt", op="setg") # use a/b (above/below) instead of g/l for unsigned
LT_FUNC = COMP_FUNC_PATTERN.format(label="lt", op="setl")
GTE_FUNC = COMP_FUNC_PATTERN.format(label="gte", op="setge")
LTE_FUNC = COMP_FUNC_PATTERN.format(label="lte", op="setle")
EQ_FUNC = COMP_FUNC_PATTERN.format(label="eq", op="sete") 
NEQ_FUNC = COMP_FUNC_PATTERN.format(label="neq", op="setne") 

BUILTIN_FUNC_ASM = (
    ADD_FUNC,
    SUB_FUNC,

    MUL_FUNC,
    DIV_FUNC,

    GT_FUNC ,
    LT_FUNC ,
    GTE_FUNC,
    LTE_FUNC,
    EQ_FUNC ,
    NEQ_FUNC,
)