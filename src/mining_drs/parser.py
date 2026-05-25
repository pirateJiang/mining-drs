import re

# We fallback to standard random/math if numpy isn't available
# for environments without third-party packages installed yet.
# TODO: i hate fallbacks remove this.
try:
    import numpy as np

    random_uniform = np.random.uniform
    random_normal = np.random.normal
    np_available = True
except ImportError:
    import random

    random_uniform = random.uniform
    random_normal = random.gauss
    np_available = False


class FormulaParser:
    """
    Parses Arena syntax expressions into compiled Python functions.
    This enables 'Fail Fast' validation during initialization and
    prevents the overhead of evaluating strings repeatedly during the simulation loop.
    """

    def __init__(self, parameters: dict):
        self.params = parameters

        # Mapped Python functions
        self.safe_globals = {
            "__builtins__": {},  # Secure the eval namespace
            "max": max,
            "min": min,
            "abs": abs,
            "random_uniform": random_uniform,
            "random_normal": random_normal,
        }

    def parse_expression(self, expression_string: str):
        """
        Converts an Arena string like "MX(NORM(param1, param2), 0)"
        into a callable Python function.
        """
        # 1. Clean the string (remove weird Excel quotes)
        clean_str = expression_string.replace('"', "").strip()

        # 2. Map Arena functions to our safe Python names
        clean_str = re.sub(r"\bUNIF\b", "random_uniform", clean_str)
        clean_str = re.sub(r"\bNORM\b", "random_normal", clean_str)
        clean_str = re.sub(r"\bMX\b", "max", clean_str)
        clean_str = re.sub(r"\bMN\b", "min", clean_str)
        clean_str = re.sub(r"\bABS\b", "abs", clean_str)

        # 3. Compile the code once. This throws SyntaxError if the expression is malformed.
        try:
            compiled_code = compile(clean_str, "<string>", "eval")

            # Fail Fast Check: Evaluate it once to catch NameErrors (e.g. typing NROM instead of NORM)
            # or missing parameters in self.params.
            eval(compiled_code, self.safe_globals, self.params)

        except NameError as e:
            raise ValueError(
                f"Unknown variable or function in expression '{expression_string}': {e}"
            )
        except Exception as e:
            raise ValueError(
                f"Failed to validate expression '{expression_string}': {e}"
            )

        # 4. Return the compiled function closure
        def executor():
            # Execution happens natively without re-evaluating the string, making it lightning-fast.
            return eval(compiled_code, self.safe_globals, self.params)

        return executor
