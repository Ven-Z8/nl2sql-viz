"""Tests for MathCalculator — the deterministic grounding tool."""

import pytest

from app.core.math_tool import MathCalculator, MathError


class TestMathCalculator:
    def setup_method(self):
        self.calc = MathCalculator()

    def test_basic_arithmetic(self):
        assert self.calc.calculate("2 + 3 * 4") == 14.0
        assert self.calc.calculate("(2 + 3) * 4") == 20.0
        assert self.calc.calculate("10 / 4") == 2.5
        assert self.calc.calculate("2 ** 10") == 1024.0

    def test_variables(self):
        assert self.calc.calculate("revenue - cost", {"revenue": 1000, "cost": 300}) == 700.0
        assert self.calc.calculate("growth / 100", {"growth": 12.5}) == 0.125

    def test_functions(self):
        assert self.calc.calculate("round(3.14159, 2)") == 3.14
        assert self.calc.calculate("sqrt(144)") == 12.0
        assert self.calc.calculate("max(1, 5, 3)") == 5.0
        assert self.calc.calculate("floor(9.9)") == 9.0
        assert self.calc.calculate("ceil(9.1)") == 10.0

    def test_comparisons(self):
        assert self.calc.calculate("0 <= x < 1", {"x": 0.5}) is True
        assert self.calc.calculate("x > 10", {"x": 5}) is False

    def test_unknown_variable_rejected(self):
        with pytest.raises(MathError, match="Unknown variable"):
            self.calc.calculate("x + 1")

    def test_arbitrary_code_rejected(self):
        # Attribute access
        with pytest.raises(MathError):
            self.calc.calculate("__import__('os').system('dir')")
        # Subscript
        with pytest.raises(MathError):
            self.calc.calculate("x[0]", {"x": [1, 2]})
        # Lambda
        with pytest.raises(MathError):
            self.calc.calculate("(lambda: 1)()")
        # Non-whitelisted function
        with pytest.raises(MathError, match="whitelisted"):
            self.calc.calculate("eval('1')")
        # String constant
        with pytest.raises(MathError):
            self.calc.calculate("'hello'")

    def test_empty_expression(self):
        with pytest.raises(MathError, match="empty"):
            self.calc.calculate("")

    def test_division_by_zero(self):
        with pytest.raises(MathError):
            self.calc.calculate("1 / 0")