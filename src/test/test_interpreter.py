import unittest

from src.interpreter import build_builtin_env, interpret_expression
from src.ast_definition import *
from src.runtime_values import *

class EvalResuts(unittest.TestCase):

    def test_operations(self):
        exp = ASTExpression(ASTBinaryOp(ASTNumber(1), ASTOp('+'), ASTNumber(1)))
        env = build_builtin_env()
        res = interpret_expression(exp, env)
        self.assertIsInstance(res, Number)
        self.assertEqual(res.value, 4)




if __name__ == "__main__":
    unittest.main()