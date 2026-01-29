"""
Runs tests for this webap.

Usage examples:
    (all) uv run ./run_tests.py -v
    (app) uv run ./run_tests.py -v pdf_checker_app
    (file) uv run ./run_tests.py -v tests.test_environment_checks
    (class) uv run ./run_tests.py -v tests.test_environment_checks.TestEnvironmentChecks
    (method) uv run ./run_tests.py -v tests.test_environment_checks.TestEnvironmentChecks.test_check_branch_non_main_raises
"""

import argparse
import importlib
import os
import sys
from pathlib import Path

import django
from django.conf import settings  # type: ignore
from django.test.utils import get_runner  # type: ignore


def main() -> None:
    """
    Discover and run tests for this webapp.
    - Uses standard library unittest (per AGENTS.md)
    - Uses Django's test runner so app-based tests (e.g., `pdf_checker_app/tests/`) are discovered
    - Sets top-level directory to the webapp root so `lib/` is importable
    """
    ## set settings as early as possible --------------------------------
    is_running_on_github: bool = os.environ.get('GITHUB_ACTIONS', '').lower() == 'true'
    if is_running_on_github:
        os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings_ci_tests'
    else:
        os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

    ## set up argparser ---------------------------------------------
    parser = argparse.ArgumentParser(description='Run webapp tests')
    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='Increase verbosity (equivalent to unittest verbosity=2)',
    )
    parser.add_argument(
        'targets',
        nargs='*',
        help=(
            'Optional dotted test targets to run, e.g. '
            '(app) `pdf_checker_app` or '
            '(module) `pdf_checker_app.tests.test_error_check` or '
            '(class/method) dotted paths under app tests'
        ),
    )
    ## parse args ---------------------------------------------------
    args = parser.parse_args()
    ## Ensure webapp root is importable (adds 'lib/', etc) ------
    webapp_root = Path(__file__).parent
    sys.path.insert(0, str(webapp_root))
    ## Change working directory to webapp root so relative discovery works
    os.chdir(webapp_root)
    settings_module = os.environ.get('DJANGO_SETTINGS_MODULE', '')
    print(
        f'DJANGO_SETTINGS_MODULE={settings_module} (GITHUB_ACTIONS={os.environ.get("GITHUB_ACTIONS", "")})',
        flush=True,
    )
    if settings_module:
        settings_mod = importlib.import_module(settings_module)
        print(f'Settings module file: {getattr(settings_mod, "__file__", None)}', flush=True)
    ## Initialize Django and use Django's test runner -----------------
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module or 'config.settings')
    django.setup()
    verbosity = 2 if args.verbose else 1
    test_labels: list[str] = list(args.targets) if args.targets else []
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=verbosity, interactive=False)
    failures = test_runner.run_tests(test_labels)
    sys.exit(0 if failures == 0 else 1)


if __name__ == '__main__':
    main()
