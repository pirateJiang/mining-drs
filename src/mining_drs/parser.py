import re

import numpy as np


class FormulaParser:
    """
    Parses Arena syntax expressions into compiled Python functions.
    This enables 'Fail Fast' validation during initialization and
    prevents the overhead of evaluating strings repeatedly during the simulation loop.
    """

    def __init__(self):
        # Mapped Python functions
        self.safe_globals = {
            "__builtins__": {},  # Secure the eval namespace
            "max": max,
            "min": min,
            "abs": abs,
            "random_uniform": np.random.uniform,
            "random_normal": np.random.normal,
        }

    def parse_expression(self, expression_string: str, init_context: dict):
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

        # 3. Handle logic operators
        clean_str = clean_str.replace("&&", " and ").replace("||", " or ")

        # 4. Compile the code once. This throws SyntaxError if the expression is malformed.
        try:
            compiled_code = compile(clean_str, "<string>", "eval")

            # Fail Fast Check: Evaluate it once to catch NameErrors (e.g. typing NROM instead of NORM)
            # or missing parameters in init_context.
            eval(compiled_code, self.safe_globals, init_context)

        except NameError as e:
            raise ValueError(
                f"Unknown variable or function in expression '{expression_string}': {e}"
            )
        except Exception as e:
            raise ValueError(
                f"Failed to validate expression '{expression_string}': {e}"
            )

        # 5. Return the compiled function closure
        def executor(live_context: dict):
            # Execution happens natively without re-evaluating the string, making it lightning-fast.
            return eval(compiled_code, self.safe_globals, live_context)

        return executor
