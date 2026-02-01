"""
Helper functions for rendering markdown content.
"""

from pathlib import Path

import markdown


def render_markdown_text(text: str) -> str:
    """
    Renders markdown text to HTML.
    """
    html: str = markdown.markdown(text, extensions=['extra'], output_format='html5')
    return html


def load_markdown_file(file_path: Path) -> str:
    """
    Loads a markdown file from disk and renders it to HTML.
    """
    markdown_text: str = file_path.read_text(encoding='utf-8')
    html: str = render_markdown_text(markdown_text)
    return html


def load_markdown_from_lib(filename: str) -> str:
    """
    Loads a markdown file stored alongside lib helpers.
    """
    lib_dir: Path = Path(__file__).resolve().parent
    file_path: Path = lib_dir / filename
    html: str = load_markdown_file(file_path)
    return html
