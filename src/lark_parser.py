import argparse
from pathlib import Path

import lark

from src.ast_definition import ASTBuilder, BlockIndenter


def initialize_parser(grammar_file: Path):
    ast_builder = ASTBuilder()
    parser = lark.Lark.open(
        str(grammar_file),
        rel_to=__file__,
        parser="lalr",
        start="module",
        lexer_callbacks=ast_builder.lexer_callbacks(),
        transformer=ast_builder,
        postlex=BlockIndenter()
        )

    # TODO: check that the full grammar has been parsed properly and not Tree object from lark are left
    return parser, ast_builder

if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--grammar-definition", default=Path(__file__).absolute().parent / "grammar.lark")
    arg_parser.add_argument("--input-file", type=Path)
    args = arg_parser.parse_args()

    parser, ast_builder = initialize_parser(args.grammar_definition)

    if args.input_file:
        res = parser.parse(Path(args.input_file).read_text())
        print(res)
        print(ast_builder.comments)
    else:
        while (cmd := input("> ")):
            try:
                res = parser.parse(cmd)
                print(res.pretty())
            except lark.LarkError as err:
                print(repr(err))
                print(err)

    