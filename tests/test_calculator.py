import unittest

from app.tools.public_tools import calculator


class CalculatorTests(unittest.TestCase):
    def test_arithmetic_and_decimal_precision(self):
        self.assertEqual(calculator("(12 + 3) * 2 ** 3")["result"], "120")
        self.assertEqual(calculator("0.1 + 0.2")["result"], "0.3")
        self.assertEqual(calculator("7 // 2")["result"], "3")

    def test_rejects_code_and_pathological_expressions(self):
        for expression in (
            "__import__('os').system('whoami')", "10 / 0", "2 ** 101", "1e999",
            "[1, 2]", "x + 1",
        ):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                calculator(expression)
