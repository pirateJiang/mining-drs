import pytest
from mining_drs.parser import FormulaParser


def test_formula_parser_compiles_valid_expression():
    params = {"param4": 10, "param5": 2}
    parser = FormulaParser()

    calc_func = parser.parse_expression('"""MX(NORM(param4, param5), 0)"""', params)

    result = calc_func(params)
    assert result >= 0
    assert isinstance(result, (int, float))


def test_formula_parser_compiles_unif_expression():
    params = {}
    parser = FormulaParser()
    calc_func = parser.parse_expression("UNIF(5, 10)", params)

    result = calc_func(params)
    assert 5 <= result <= 10


def test_formula_parser_fails_fast_on_syntax_error():
    parser = FormulaParser()

    with pytest.raises(ValueError, match="Failed to validate expression"):
        parser.parse_expression("MX(NORM(1, 2), 0", {})


def test_formula_parser_fails_fast_on_name_error():
    parser = FormulaParser()

    with pytest.raises(ValueError, match="Unknown variable or function in expression"):
        parser.parse_expression("MX(NROM(1, 2), 0)", {})


def test_formula_parser_fails_fast_on_missing_parameter():
    params = {"param1": 10}
    parser = FormulaParser()

    with pytest.raises(ValueError, match="Unknown variable or function"):
        parser.parse_expression("MX(param1, param2)", params)
