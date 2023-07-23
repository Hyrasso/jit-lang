from typing import Any
from dataclasses import dataclass

@dataclass
class TypedVar:
    value: Any
    typ: Any


class Environment:
    def __init__(self, parent=None, env=None) -> None:
        self.parent = parent
        self._env = env if env is not None else {}

    def get(self, val):
        if val in self._env:
            return self._env[val].value
        
        if self.parent is not None:
            return self.parent.get(val)
        
        raise RuntimeError(f"Unknown {val} in env")

    def get_typ(self, val):
        if val in self._env:
            return self._env[val].typ
        
        if self.parent is not None:
            return self.parent.get(val)
        
        raise RuntimeError(f"Unknown {val} in env")

    def update(self, var, val):
        if var in self._env:
            self._env[var].value = val
        else:
            if self.parent is None:
                raise RuntimeError(f"Assigning to undeclared var {var}")
            else:
                self.parent.update(var, val)

    # systematicaly shadow parent env
    def set(self, var, val, typ):
        # also shadow var in the same environement, the shadowed var is not accessible anymore after this
        self._env[var] = TypedVar(val, typ)

