from jinja2 import nodes
from jinja2.ext import Extension
from jinja2.parser import Parser

from port_ocean import __version__


# Used to extend the cookiecutter syntax and allow the template to use ocean version in it using `{% version %}`
class VersionExtension(Extension):
    tags = {"version"}

    def parse(self, parser: Parser) -> nodes.Node | list[nodes.Node]:
        return nodes.Const(__version__, lineno=next(parser.stream).lineno)
