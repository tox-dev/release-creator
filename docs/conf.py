"""Sphinx project settings."""

from importlib.metadata import version as package_version
from pathlib import Path
from tomllib import loads
from typing import TYPE_CHECKING, cast, override

from pygments.lexers.shell import BashLexer
from pygments.token import Name, Text, _TokenType

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sphinx.application import Sphinx

project = "release-creator"
release = package_version(project)
extensions = ["sphinx.ext.extlinks", "sphinx_argparse_cli", "sphinx_copybutton", "sphinxcontrib.mermaid"]
source_suffix = ".rst"
extlinks = {
    "pr": ("https://github.com/tox-dev/release-creator/pull/%s", "#%s"),
    "user": ("https://github.com/%s", "@%s"),
}
html_theme = "furo"
html_title = project
html_logo = "_static/logo-128.png"
html_favicon = "_static/favicon.png"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
nitpicky = True
exclude_patterns = ["_build"]


def setup(app: Sphinx) -> None:
    """Color Bash examples and show unreleased changelog entries."""
    app.add_lexer("bash", CommandLexer)
    app.connect("source-read", include_unreleased)


class CommandLexer(BashLexer):
    """Promote Bash words that Pygments leaves unstyled."""

    @override
    def get_tokens_unprocessed(
        self, text: str, stack: tuple[str, ...] = ("root",)
    ) -> Iterator[tuple[int, _TokenType, str]]:
        """Yield Bash tokens with commands and options marked for color.

        :param text: Bash source to highlight.
        :param stack: Lexer state stack.
        :yield: Token offsets, kinds, and text.
        """
        for index, token, value in super().get_tokens_unprocessed(text, stack):
            if token in Text and value.startswith("--"):
                highlighted_token = Name.Attribute
            elif token in Text and value in {"uvx", "git", "gh", "towncrier", "release-creator"}:
                highlighted_token = Name.Builtin
            else:
                highlighted_token = token
            yield cast("tuple[int, _TokenType, str]", (index, highlighted_token, value))


def include_unreleased(app: Sphinx, docname: str, source: list[str]) -> None:
    """Show fragments in previews before Towncrier consumes them."""
    if docname != "changelog":
        return
    root = Path(__file__).parent.parent
    fragments = root / "changelog.d"
    app.env.note_dependency(str(fragments))
    categories = loads((root / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["towncrier"]["type"]
    sections = []
    for category in categories:
        entries = []
        for fragment in sorted(fragments.glob(f"*.{category['directory']}.rst")):
            app.env.note_dependency(str(fragment))
            entry = fragment.read_text(encoding="utf-8").strip().replace("\n", "\n  ")
            entries.append(f"- {entry}")
        if entries:
            sections.extend((
                f".. _release-unreleased-{category['name'].lower().replace(' ', '-')}:",
                "",
                category["name"],
                "~" * len(category["name"]),
                "",
                *entries,
                "",
            ))
    if sections:
        draft = "\n".join(sections)
        source[0] = source[0].replace(
            ".. towncrier release notes start",
            f".. _release-unreleased:\n\nUnreleased\n----------\n\n{draft}.. towncrier release notes start",
        )
