
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

