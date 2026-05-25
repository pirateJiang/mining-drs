import pytest
from mining_drs.parser import FormulaParser


def test_formula_parser_compiles_valid_expression():
    params = {"param4": 10, "param5": 2}
    parser = FormulaParser(params)

    # Valid Arena syntax: """MX(NORM(param4, param5), 0)"""
    # MX maps to max, NORM maps to random_normal (or np.random.normal)
    calc_func = parser.parse_expression('"""MX(NORM(param4, param5), 0)"""')

    result = calc_func()
    # It's a normal distribution (mean 10, std 2), max with 0
    assert result >= 0
    assert isinstance(result, (int, float))


def test_formula_parser_compiles_unif_expression():
    params = {}
    parser = FormulaParser(params)
    calc_func = parser.parse_expression("UNIF(5, 10)")

    result = calc_func()
    assert 5 <= result <= 10


def test_formula_parser_fails_fast_on_syntax_error():
    parser = FormulaParser({})

    # Missing closing parenthesis
    with pytest.raises(ValueError, match="Failed to validate expression"):
        parser.parse_expression("MX(NORM(1, 2), 0")


def test_formula_parser_fails_fast_on_name_error():
    parser = FormulaParser({})

    # NROM instead of NORM
    with pytest.raises(ValueError, match="Unknown variable or function in expression"):
        parser.parse_expression("MX(NROM(1, 2), 0)")


def test_formula_parser_fails_fast_on_missing_parameter():
    params = {"param1": 10}
    parser = FormulaParser(params)

    # param2 is missing
    with pytest.raises(ValueError, match="Unknown variable or function"):
        parser.parse_expression("MX(param1, param2)")
