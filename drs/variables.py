import math
from typing import Any, Union
from .execution_context import ExecutionContext


class Expression:
    """AST node for tracking mathematical dependencies between Variables."""

    def __init__(self, op: str, left: Any, right: Any):
        self.op = op
        self.left = left
        self.right = right

    def evaluate(self) -> float:
        def get_val(node):
            if isinstance(node, Expression):
                return node.evaluate()
            if hasattr(node, "value"):
                return node.value
            return node

        l_val = get_val(self.left)
        r_val = get_val(self.right)

        if self.op == "add":
            return l_val + r_val
        if self.op == "sub":
            return l_val - r_val
        if self.op == "mul":
            return l_val * r_val
        if self.op == "div":
            return l_val / r_val if r_val != 0 else 0.0
        if self.op == "gt":
            return l_val > r_val
        if self.op == "lt":
            return l_val < r_val
        if self.op == "ge":
            return l_val >= r_val
        if self.op == "le":
            return l_val <= r_val
        if self.op == "eq":
            return l_val == r_val
        if self.op == "ne":
            return l_val != r_val
        return 0.0

    def get_sources(self) -> list:
        sources = set()
        for side in (self.left, self.right):
            if hasattr(side, "get_sources"):
                sources.update(side.get_sources())
        return list(sources)

    def get_equation(self) -> str:
        op_chars = {
            "add": "+", "sub": "-", "mul": "*", "div": "/",
            "gt": ">", "lt": "<", "ge": ">=", "le": "<=",
            "eq": "==", "ne": "!=",
        }

        def format_node(node):
            if isinstance(node, Expression):
                return node.get_equation()
            if hasattr(node, "name"):
                mod = getattr(node, "_owner", None)
                if mod and hasattr(mod, "name"):
                    return f"{mod.name}.{node.name}"
                elif mod:
                    return f"{type(mod).__name__}.{node.name}"
                return node.name
            return str(node)

        return f"({format_node(self.left)} {op_chars.get(self.op, '?')} {format_node(self.right)})"

    def __bool__(self):
        raise TypeError(
            f"Cannot use Expression ('{self.get_equation()}') as a boolean. "
            f"Use `.value` for immediate evaluation or `drs.Where()` for symbolic branching."
        )

    def __add__(self, other): return Expression("add", self, other)
    def __sub__(self, other): return Expression("sub", self, other)
    def __mul__(self, other): return Expression("mul", self, other)
    def __truediv__(self, other): return Expression("div", self, other)
    def __radd__(self, other): return Expression("add", other, self)
    def __rsub__(self, other): return Expression("sub", other, self)
    def __rmul__(self, other): return Expression("mul", other, self)
    def __rtruediv__(self, other): return Expression("div", other, self)
    def __gt__(self, other): return Expression("gt", self, other)
    def __lt__(self, other): return Expression("lt", self, other)
    def __ge__(self, other): return Expression("ge", self, other)
    def __le__(self, other): return Expression("le", self, other)
    def __eq__(self, other): return Expression("eq", self, other)
    def __ne__(self, other): return Expression("ne", self, other)


class Variable:
    """Base class for all domain variables."""

    def __init__(self, name: str, initial_value: Any = 0.0):
        self.name = name
        self._value = initial_value
        self._owner = None

    def _sim_value(self):
        if isinstance(self._value, Expression):
            return self._value.evaluate()
        return self._value

    def _record_read_dependency(self):
        current = ExecutionContext.get_current()
        if current is not None and current is not self._owner:
            current._record_incoming_edge(self)

    @property
    def value(self):
        self._record_read_dependency()
        return self._sim_value()

    @value.setter
    def value(self, val):
        current = ExecutionContext.get_current()
        if current is not None and current is not self._owner:
            raise RuntimeError(
                f"Illegal Mutation: {type(current).__name__} tried to mutate "
                f"'{self.name}' owned by {type(self._owner).__name__}. "
                f"Modules must communicate by passing Signals/Flows. Do not mutate state directly!"
            )
        self._value = val

    def get_sources(self) -> list:
        return [self]

    def __hash__(self):
        return id(self)

    def _op(self, op: str, other):
        self._record_read_dependency()
        if isinstance(other, Variable):
            other._record_read_dependency()
        if ExecutionContext.is_tracing():
            return Expression(op, self, other)
        r_val = other._sim_value() if isinstance(other, Variable) else other
        l_val = self._sim_value()
        if op == "add": return l_val + r_val
        if op == "sub": return l_val - r_val
        if op == "mul": return l_val * r_val
        if op == "div": return l_val / r_val if r_val != 0 else 0.0
        if op == "gt": return l_val > r_val
        if op == "lt": return l_val < r_val
        if op == "ge": return l_val >= r_val
        if op == "le": return l_val <= r_val
        if op == "eq": return l_val == r_val
        if op == "ne": return l_val != r_val
        return NotImplemented

    def _rop(self, op: str, other):
        if ExecutionContext.is_tracing():
            return Expression(op, other, self)
        l_val = other._sim_value() if isinstance(other, Variable) else other
        r_val = self._sim_value()
        if op == "add": return l_val + r_val
        if op == "sub": return l_val - r_val
        if op == "mul": return l_val * r_val
        if op == "div": return l_val / r_val if r_val != 0 else 0.0
        return NotImplemented

    def __add__(self, other): return self._op("add", other)
    def __sub__(self, other): return self._op("sub", other)
    def __mul__(self, other): return self._op("mul", other)
    def __truediv__(self, other): return self._op("div", other)
    def __radd__(self, other): return self._rop("add", other)
    def __rsub__(self, other): return self._rop("sub", other)
    def __rmul__(self, other): return self._rop("mul", other)
    def __rtruediv__(self, other): return self._rop("div", other)
    def __gt__(self, other): return self._op("gt", other)
    def __lt__(self, other): return self._op("lt", other)
    def __ge__(self, other): return self._op("ge", other)
    def __le__(self, other): return self._op("le", other)
    def __eq__(self, other): return self._op("eq", other)
    def __ne__(self, other): return self._op("ne", other)


class Level(Variable):
    """A variable that accumulates over time based on a rate."""

    def __init__(self, name: str, initial_value: float = 0.0, rate: float = 0.0):
        super().__init__(name, initial_value)
        self._rate = rate
        self.upper_threshold = math.inf
        self.lower_threshold = -math.inf

    @property
    def rate(self) -> float:
        if isinstance(self._rate, Expression):
            return self._rate.evaluate()
        return self._rate

    @rate.setter
    def rate(self, val):
        if isinstance(val, tuple):
            if len(val) == 3:
                self._rate, self.lower_threshold, self.upper_threshold = val
            else:
                raise ValueError(f"Rate tuple must be (rate, lower, upper), got {val}")
        else:
            self._rate = val

    def update(self, dt: float):
        self.value += self.rate * dt


class Timer(Level):
    """A specialized level used to track time, typically with a rate of 1.0 or -1.0."""

    def __init__(self, name: str, initial_value: float = 0.0, rate: float = 1.0):
        super().__init__(name, initial_value, rate)

    def reset(self):
        self.value = 0.0
