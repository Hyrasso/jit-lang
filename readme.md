# Interpreter and jit compiling for homemade lang

Python 3.11, dependencies in requirements.txt  
Requires gcc to compile jitted code (currently using `gcc (Ubuntu 9.4.0-1ubuntu1~20.04.1) 9.4.0`)

Usage exemple: `python src/interpreter.py --input-file examples/fibo.jil --jit-compile`

## TODO
- add struct and array
- do some type checking
- getc/putc for compilation
- inline some ast functions
