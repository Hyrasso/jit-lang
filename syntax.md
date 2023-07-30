
# variables 

    a : int = 3

    f : (int, int) int = fn(x: int, y: int) int:
        x + y


# Branches and loops

No for loop for now

    age: int = 123
    if age >= 18:
        print("is major")
    else if age < 0: # not implemented yet
        print("uh?")
    else:
        print("is not major")
    
    while age > 18:
        age -= 1

# Scoping and shadowing

    a: Mut(int) = 3
    a: float = 6.4 # shadowing variables is ok

    is_more_than_2: Mut(int) = 2
    if a > 2:
        is_more_than_2 := true # shadowing
        a = 2
    else:
        is_less_than_2 := true
    # here: a = 2, is_more_than_2 = 2

# builtin types

    u8 - u64
    i8 - i64
    f32 - f64
    [...], [..., N]
    Struct
    Enum

    # functions, eg
    (u8, u8) u8
    # there is no parent function type like for struct and enum? Fn maybe?

    # to create mutable variables/objects
    Mut

    # to create references
    Ref
    

# Structs

    Pair: struct = {a: int, b: int}
    s: Pair = {a: 1, b: 3}
    # or
    s2: {a: int, b: int} = {a: 3, b: 1}

    val: int = s.a

    s2.b = val

`.` works on struct, and nested struct to get values.

# Enum

Actually the symbol thing doesnt work that much? -> empty structs instead
Its cool for the #false for example, but if a type is equal only with itself it could be done with anything. Still nice to have a zero size type probably.
Keep the idea of symbols? Symbol is the parent, and each symbol is also a type? like struct and {a: int, b: int} -> None: Symbol = symbol() ?
Instead of symbols, just allow empty structs and rely on nominay typing

    None: {}
    Some: Enum = {value: int | None: None}
    
    contains_value: Some = {value: 2}
    is_none: Some = {None: {}}


# Arrays

The fixed size array is not necessary, it is the same as a struct with N fields

    # fixed size
    a: [int, 4] = [1, 2, 3, 4]

    val = a[1]
    a[0] = val - a[0]

    # slices
    first := f(a: [int]) int: a[0] # could raise an error

[] accessing is a wrapper around an underlying `get`

    get := (a: [ int ], idx: int) Some(int):
        res: Some(int) = {None: Some.None}
        if idx < a.length:
            res = a.raw_get(idx) # or a.addr + idx * sizeof(a.elem_type)
        res
    
    [] := (a: [ int ], idx: int) int:
        res = a.get(idx)
        if res == Some.None:
            panic()
        res.value

# References

To rethink, are references necessary? Should they be box and point to the heap, and no ability to define reference to the stack (the compiler could optimize when necessary)? What are the uses for references, aside performance (because this one does not matter)?

When assigning values to variables they are always copied, unless it is a ref
For now acessing the inner obj requires using *, add syntactic sugar in the future?

A ref is kind of a ```Struct: {pointer: u64, operator`*`: () someType }```, so assigining/copying only copies the struct/pointer and `*` needs to be used to get access to the underlying object

References are created on the heap, and should be freed, but its unclear how for now.

Do not use similar syntax as the one for array, as they should be clearly seperate from arrays semantically (eg arrays are passed by copy, where for mutable reference the semantics are different)


    # not that usefull because the value cannot be modified, probably most usefull to avoid copy when calling functions
    a: Ref(int) = make_ref(1)
    b: Ref(int) = a.get_ref()

    o: Ref(HeavyObject) = ...
    f: (Ref(HeavyObject)) int: = (obj: Ref(HeavyObject)) int:
        some_computation(obj*.attr)
    
    # still not very usefull, maybe for traversing an immutable linked list for example?
    a: Mut(Ref(int)) = make_ref(1)

    # now it gets interesting
    a: Ref(Mut(int)) = make_mut_ref(1)
    b: Ref(Mut(int)) = a # should that be allowed
    b* = b* + 1 # a -> 2

    f: (Ref(Mut(int))) = (inout: Ref(Mut(int))):
        inout* = 3
    a: Ref(Mut(int)) = make_mut_ref(1)
    f(a)
    # now a -> 3


# Mutability

    # Everything is immutable by default
    # To create a mutable variable use Mut

    a: Mut(int) = 2
    b: int = 3

    a = 3 # ok
    b = 2 # not ok

    # ok
    D: int = 5
    f: (int) int = (x: int) int:
        x + D

    # not ok, until closure are implemented
    D: Mut(int) = 5
    f: (int) int = (x: int) int:
        x + D
    # because what happens then?
    D = 4
    f(1) # ???

When converting between non mut and mut, the value is copied (on assigning to something else than a ref, the valus is always copied)

    C: int = 1
    a: Mut(int) = C # copy C here
    a = 2 # have no effect on C
    b: Mut(int) = a
    b = 3 # have no effect on a

Mutability can be defined for struct fields

    S : struct = {
        a: mut(int),
        b: int
    }

    s1 : S = {a: 1, b: 2}
    s1.a = 3 # error
    s1 : mut(S) = {a: 1, b: 2}
    s1.a = 3 # ok
    s1.b = 3 # error

This seems a bit annoying if we want to allow all fields to be mutable, but it would be possible to just write a function that returns all fields wrapped in mut `S : struct = with_mutable_fields({a: int, b: int})``


## Interactions when composing with other types

Mut is not allowed for members of struct, enums and arrays, the full thing is mutable or it isnt

## Some impact on functions

    f: (Mut(Person)) = (x: Mut(Person)):
        x.age = x.age + 1
        x

    # enforces call by copy here
    p := {age: 123, name: "Bob"}
    f(p) # -> 124
    # p.age is still 123

    f: () Mut(int) = () Mut(int): 1
    a: Mut(int) = f()
    a = 2
    f() # still 1

    # not allowed for now, but in the future should it capture?
    cap: Mut(int) = 1
    f: (int) = (x: int) int:
        cap = cap + 1
        x + cap




# modules

A module is a struct, import is a builtin that returns a struct instance with a type that depends on the argument

    math := import("math")
    cos: (float) float = math.cos