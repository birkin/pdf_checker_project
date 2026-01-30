import datetime
import logging
import pathlib
import pprint

import trio
from django.conf import settings

log = logging.getLogger(__name__)


def make_context(request, rq_now, info_txt):
    """
    Assembles data-dct.
    Called by:
        - views.version()
    """
    context = {
        'request': {
            'url': '%s://%s%s'
            % (
                request.scheme,
                request.META.get('HTTP_HOST', '127.0.0.1'),  # HTTP_HOST doesn't exist for client-tests
                request.META.get('REQUEST_URI', request.META['PATH_INFO']),
            ),
            'timestamp': str(rq_now),
        },
        'response': {
            'ip': request.META.get('REMOTE_ADDR', 'unknown'),
            'version': info_txt,
            'timetaken': str(datetime.datetime.now() - rq_now),
        },
    }
    return context


class GatherCommitAndBranchData:
    """
    Note:
    - Originally this class made two separate asyncronous subprocess calls to git.
    - Now it reads the `.git/HEAD` file to get the commit and branch data, so it doesn't need to be asyncronous.
    """

    def __init__(self):
        self.commit_data = ''
        self.branch_data = ''

    async def manage_git_calls(self):
        """
        Triggers separate version and commit preparation concurrently.
        - Originally this class made two separate asyncronous subprocess calls to git.
        - Now it reads the `.git/HEAD` file to get both the commit and branch data (to avoid the `dubious ownership` issues),
          so it no longer benefits from asyncronous calls, but keeping for reference.
        Called by:
            - views.version()
        """
        log.debug('manage_git_calls')
        results_holder_dct = {}  # receives git responses as they're produced
        async with trio.open_nursery() as nursery:
            nursery.start_soon(self.fetch_commit_data, results_holder_dct)
            nursery.start_soon(self.fetch_branch_data, results_holder_dct)
        log.debug(f'final results_holder_dct, ```{pprint.pformat(results_holder_dct)}```')
        self.commit = results_holder_dct['commit']
        self.branch = results_holder_dct['branch']
        log.debug(f'self.branch, ``{self.branch}``')
        return

    async def fetch_commit_data(self, results_holder_dct):
        """
        Fetches commit-data by reading the `.git/HEAD` file (avoiding calling git via subprocess due to `dubious ownership` issue).
        Called by:
            - manage_git_calls()
        """
        log.debug('fetch_commit_data')
        git_dir = pathlib.Path(settings.BASE_DIR) / '.git'
        try:
            ## read the HEAD file to find the current branch ------------
            head_file: pathlib.Path = git_dir / 'HEAD'
            ref_line: str = head_file.read_text().strip()
            if ref_line.startswith('ref:'):
                ref_path = ref_line.split(' ')[1]  # extract the ref path
                commit_file: pathlib.Path = git_dir / ref_path
                commit: str = commit_file.read_text().strip()
            else:  # if it's a detached HEAD, the commit hash is directly in the HEAD file
                commit: str = ref_line
        except FileNotFoundError:
            log.error('no `.git` directory or HEAD file found.')
            commit = 'commit_not_found'
        except Exception:
            log.exception('other problem fetching commit data')
            commit = 'commit_not_found'
        log.debug(f'commit, ``{commit}``')
        ## update holder --------------------------------------------
        results_holder_dct['commit'] = commit
        return

    async def fetch_branch_data(self, results_holder_dct):
        """
        Fetches branch-data by reading the `.git/HEAD` file (avoiding calling git via subprocess due to `dubious ownership` issue).
        Called by:
            - manage_git_calls()
        """
        log.debug('fetch_branch_data')
        git_dir = pathlib.Path(settings.BASE_DIR) / '.git'
        try:
            ## read the HEAD file to find the current branch ------------
            head_file = git_dir / 'HEAD'
            ref_line = head_file.read_text().strip()
            if ref_line.startswith('ref:'):
                branch = ref_line.split('/')[-1]  # extract the branch name
            else:
                branch = 'detached'
        except FileNotFoundError:
            log.error('no `.git` directory or HEAD file found.')
            branch = 'branch_not_found'
        except Exception:
            log.exception('other problem fetching branch data')
            branch = 'branch_not_found'
        ## update holder --------------------------------------------
        results_holder_dct['branch'] = branch
        return


## end class GatherCommitAndBranchData
