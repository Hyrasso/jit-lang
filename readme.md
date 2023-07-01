# Interpreter and jit compiling for homemade lang

Python 3.11, dependencies in requirements.txt  
Requires gcc to compile jitted code (currently using `gcc (Ubuntu 9.4.0-1ubuntu1~20.04.1) 9.4.0`)

Usage exemple: `python src/interpreter.py --input-file examples/simple_compilation_example.jil --jit-compile`

## TODO
- loops
- clarify scoping rules, for now every indent is a new scope, but that is limiting
    Options:
    - single scope for each function body (messy, maybe not that easy to implement because might need to scan for all variables when jitting func)
    - differentiate between declaration and assignement (introduce typing and grammar like a: int = 3)
    - cannot spill to parent scope but can modify in parent scope (would make the most sense when jitted)