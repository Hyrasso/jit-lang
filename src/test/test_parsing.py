import unittest
from pathlib import Path

from src.lark_parser import initialize_parser

from src.ast_definition import *

GRAMMAR_FILE = Path("grammar.lark")

class Parseing(unittest.TestCase):

    def setUp(self) -> None:
        parser, ast_builder = initialize_parser(GRAMMAR_FILE)
        self.parser = parser
        self.ast_builder = ast_builder
    
    def unpack_single_statement(self, module: ASTModule) -> ASTStatement:
        self.assertIsInstance(module, ASTModule)
        self.assertIsInstance(module.value, ASTBlock)
        self.assertEqual(len(module.value.value), 1)
        stmt = module.value.value[0]
        self.assertIsInstance(stmt, ASTStatement)
        return stmt

    def test_module(self):
        ast: ASTModule = self.parser.parse("1\n")
        stmt = self.unpack_single_statement(ast)
        self.assertIsInstance(stmt.value, ASTExpression)

    def test_number(self):
        for num, val in (("1", 1), ("0", 0)):
            with self.subTest(num):
                ast: ASTModule = self.parser.parse(f"{num}\n")
                stmt = self.unpack_single_statement(ast)
                self.assertIsInstance(stmt.value, ASTExpression)
                exp = stmt.value
                self.assertIsInstance(exp.value, ASTNumber)
                num = exp.value
                self.assertEqual(num.value, val)


if __name__ == "__main__":
    unittest.main()