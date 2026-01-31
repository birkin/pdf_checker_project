"""
Updates the pattern header HTML from a remote source.

The raw html is saved to `lib/pattern_header_upstream.html`.

Slight parsing is then done to extract the head and body fragments to ensure valid html after the includes.
- The head fragment is saved to `pdf_checker_app_templates/pdf_checker_app/includes/pattern_header/head.html`.
- The body fragment is saved to `pdf_checker_app_templates/pdf_checker_app/includes/pattern_header/body.html`.

Usage:
    python manage.py update_pattern_header

Notes:
- This update will be run **manually only** (never auto-run).
- The `PATTERN_HEADER_URL` setting comes from the `.env`.
- The `PATTERN_HEADER_URL` source is considered **trusted**.
"""

import pathlib
from argparse import ArgumentParser

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand


def fetch_pattern_header(url: str) -> str:
    """
    Fetches pattern header HTML from the given URL.
    """
    response: httpx.Response = httpx.get(url, timeout=30.0)
    response.raise_for_status()
    return response.text


def resolve_target_paths() -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    """
    Resolves the target paths for the pattern header files.
    """
    app_dir: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent.parent
    upstream_path: pathlib.Path = app_dir / 'lib' / 'pattern_header_upstream.html'
    template_dir: pathlib.Path = app_dir / 'pdf_checker_app_templates' / 'pdf_checker_app' / 'includes' / 'pattern_header'
    head_path: pathlib.Path = template_dir / 'head.html'
    body_path: pathlib.Path = template_dir / 'body.html'
    return upstream_path, head_path, body_path


def split_pattern_header(content: str) -> tuple[str, str]:
    """
    Splits the upstream pattern header into head and body fragments.
    """
    target_link = '<link rel="stylesheet" href="https://dlibwwwcit.services.brown.edu/common/css/bul_patterns.css"/>'
    target_line = f'{target_link}\n'
    head_content = ''
    body_content = content

    if target_line in content:
        head_content = f'{target_link}\n'
        body_content = content.replace(target_line, '', 1)
    elif target_link in content:
        head_content = f'{target_link}\n'
        body_content = content.replace(target_link, '', 1)

    return head_content, body_content


def save_pattern_header(content: str, target_path: pathlib.Path) -> None:
    """
    Saves pattern header HTML to the target file.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding='utf-8')


class Command(BaseCommand):
    """
    Updates the pattern header HTML from a remote source.
    """

    help = 'Updates the pattern header HTML from PATTERN_HEADER_URL'

    def add_arguments(self, parser: ArgumentParser) -> None:
        """
        Adds command-line arguments.
        """
        parser.add_argument(
            '--url',
            type=str,
            help='Override URL from settings',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Fetch but do not save',
        )

    def handle(self, *args: object, **options: object) -> None:
        """
        Executes the command.
        """
        options_dict: dict[str, object] = options
        url_option = options_dict.get('url')
        url_override = url_option if isinstance(url_option, str) else ''
        url: str = url_override or getattr(settings, 'PATTERN_HEADER_URL', '')
        if not url:
            self.stdout.write(self.style.ERROR('PATTERN_HEADER_URL not set in settings and --url not provided'))
            return

        dry_run = bool(options_dict.get('dry_run'))
        upstream_path, head_path, body_path = resolve_target_paths()

        self.stdout.write(f'Fetching pattern header from: {url}')
        try:
            content = fetch_pattern_header(url)
        except httpx.HTTPError as exc:
            self.stdout.write(self.style.ERROR(f'Failed to fetch: {exc}'))
            return

        self.stdout.write(f'Fetched {len(content)} characters')
        head_content, body_content = split_pattern_header(content)

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run - not saving'))
            return

        save_pattern_header(content, upstream_path)
        save_pattern_header(head_content, head_path)
        save_pattern_header(body_content, body_path)
        self.stdout.write(self.style.SUCCESS(f'Saved upstream snapshot to: {upstream_path}\n'))
        self.stdout.write(self.style.SUCCESS(f'Saved head include to: {head_path}\n'))
        self.stdout.write(self.style.SUCCESS(f'Saved body include to: {body_path}\n'))
