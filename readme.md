# Interpreter and jit compiling for homemade lang

Python 3.11, dependencies in requirements.txt  
Requires gcc to compile jitted code (currently using `gcc (Ubuntu 9.4.0-1ubuntu1~20.04.1) 9.4.0`)

Usage exemple: `python src/interpreter.py --input-file examples/fibo.jil --jit-compile`

## TODO

- first class function (check that they can be reassigned and passed as argument and called inside other functions)
    clarify a bit how that works if types only match themselves (is function declaration a value, that can be cast to match the function type?)
- add location in file to ast nodes for debugging
- ensure type checking works as expected for functions
- implement that types are not compared structurally, but only if they are exactly the same (casting should happend only on assignment from literal, the rest of the time the types should match exactly)
- add fixed size array (very similar to struct)
- fix end of line comments (currently `1 + 1 # comment` breaks the parsing)
- add slice? (a fat pointer, so a struct with a size + a pointer) (needs to think about where the backing memory comes from, a fixd size array?)
- read/write for compilation to have print/file read at compile time
- inline some ast functions during compilation
- seperate the ASTNodes and the runtime values (-> generate a simple bytecode from the ast)

## ideas

- types are only equal with themselves (nomincal typing, as opposed to structural sypting), so when defining a function `f: () {a: u64} = () {a: u64}` would raise an error.

- Should mutability be linked to the variable/the name, or with the type itself?
    When linked with the type it is weird with struct, eg it allows for inner mutability of an immutable variable
    ```
        S: Struct = {a: Mut(int)}
        s: S = {a: 1}
        s = {a: 2} # not allowed
        s.a = 2 # allowed?
    ```
    also weird with functions
    ```
        f: (int) Mut(int) = (x: int) Mut(int) = x + 1
    ```
    But when its a variable attribute how to define a `ref(mut int)` and not a `mut ref(int)`

- references
    what are references, why are they needed
    references are only allowed to immutable data? when mutating something its necessary to take ownership?
    how are they 'freed', if they are the memory behind
    Do not use [] for references, as we the semantics should be clearly seperated from arrays ones. & or * are fine if a specific operator is needed.
    - Using a garbage collector / reference counting?
    - Manually?

- memory
    how to allocate memory with an unknown size at compile time (an array with runtime size, an vector that can grow during runtime)
    - Box kind of type?

- How to call 'methods' without classes
    - when `f(self: int) int` is defined allow to call it as 1.f(), annoying as the `.` becomes more complicated than just a member access
    - structs have can have function members, and when the first argument is the type of the struct implicitely pass it as argument `s.f()` becomes `s.f(s)` if `f: (self: typeof(s))`
        How to get the type of the outer struct when defining a method?
    - have a way to signal that a function is actually a method vs just a member that is a function in the definition `method f: (self: Self): self.attr + 1`, or `f: method(self: Self): self.attr + 1`


- As the language is interpreted, but has capability for JIT compilation, how to compile a program?
    The language has a 'jit' module that can produce compiled artifacts, the compiled artifact can be read and executed by the interpreter.
    So to compile a program, it should call the 'jit.compile' on the function to be compiled, (potentially the entrypoint) and when distributed the artifacts should be associated.
    In theory the interpreter is still required even when the whole program is pre-compiled, but in practice it would be possible to distibute a lightweight wrapper that just calls the compiled code. So the compilation would be: call 'jit.compile' on the function, then call a 'create_executable' function that create a single executable form the artifact + the startup procedure pointing to the right function. All that could be done under a 'compile mode' flag that skips the actual entry point call, and it would be possible to run the exact same program with the interpreter by skipping the jit+compilation and calling the entrypoint instead.

- boostrap
    Rewrite the parser, interpreter and jit compilation, then compile the entrypoint using the python implementation, write a small executable that calls the compiled entrypoint, then run a program (eg the interpreter)

- async code
    Functions can use `suspend` to mark points where they can pause execution give control back to the caller.
    async functions can be started using `async f()`, it returns an object (a future) that has a `next()` that returns an enum (suspendExecution, return type) and an `await()` (not necassry, easy to reimplement) method that calls `next()` until it gets the return type and returns the result.
    `.next()` can be called manually, or used by a scheduler/event loop for example.
    If the function is a normal function using `async` will just call the function on `async` and return the result directly on the first `.next()`. So same for `.next()` that returns directly. All the code before the first `next()` is run when `async` is called. A sync function without `suspend` just directly runs until the return.
    If a function that contains `suspend` is called like a normal function, `suspend`s are just ignored.
    What about the type system, should a function that contains suspends be marked in some way or should it be completely invisible for the caller? (it seems like it would be nice to be able to know if the functions supports async), maybe all function call should be async behind the scene, and if theres no async keyword generate `(async f()).await()`, so no specific type, all functions are async, just some do not use suspend. Then for those it would be possible to optimize the calls to avoid creating a function frame.
    Following zig, next could be called resume instead, and that would avoid confusion with generators

- generator
    similar to async, `next` returns an enum (yield type, return type), what is the difference between calling a generator with async or not then? what about the type of a generator, the yield type should be in the function type, or enforce the same type as the return type, and return an enum if we want different types. The issue is that generator are different enough with async function because we cannot just discard the `next()` return values by default, also calling a normal function like a generator do not work -> generator needs to be their own specific objects/types, different than async code. If they are different, should they share the syntax/interface (yield, next?)
    Can generator be implemented using async code? something like passing an inout variable, and inside the generator do `inout_var[] = value_to_yield ; syspend ;` so that after `next()` return we have access to the yielded value from the outside, we could even send values to be read after tye yield resumes in the function. When calling this type of function without async yield are ignored so the value read is the value sent (maybe when we went to read values have a separate `inout_var` to avoid that) so the wrapper should ensure the function is called with (async f()).

- seperate ast from interpretation
    Would seperate the syntax from the underlying language semantics and runtime values
    In a first time have a simple pass that generates a bytecode that is equivalent to the AST, with some nodes like astnumber or astfunctiondeclare moved to their runtime values
    The bytecode can be the flattened AST, represented as a list, with instead of children as fields, children as offsets in the bytecode
    The interpreter could still have a structure of recursive functions in a first time, but with a current idx being passed around to get the children. The match would still be usable aswell
