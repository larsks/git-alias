from enum import Enum
import sh


class Target(Enum):
    '''Constants that correspond to git config's --system, --global,
    --local, and --worktree command line options.'''
    SYSTEM = 1
    GLOBAL = 2
    LOCAL = 3
    WORKTREE = 4


class Git:
    def __init__(self, target=Target.GLOBAL):
        self.target = target
        self.git = sh.git.bake('--no-pager')
        self.gitconfig = self.git.bake('config', *self.common_args)

    @property
    def common_args(self):
        args = []
        target = self.target

        if target is Target.SYSTEM:
            args.append('--system')
        elif target is Target.GLOBAL:
            args.append('--global')
        elif target is Target.LOCAL:
            args.append('--local')
        elif target is Target.WORKTREE:
            args.append('--worktree')
        else:
            args.extend(('--file', target))

        return args

    def list_aliases(self):
        res = self.gitconfig('--list', '--name-only')
        for line in res.stdout.decode().splitlines():
            section, name = line.split('.', 1)
            if section != 'alias':
                continue

            yield name

    def get_alias(self, name):
        res = self.gitconfig('--get', 'alias.{}'.format(name))
        return res.stdout.decode().strip()

    def set_alias(self, name, value):
        self.gitconfig('alias.{}'.format(name), value)

    def remove_alias(self, name):
        try:
            self.gitconfig('--unset', 'alias.{}'.format(name))
        # pylint: disable=no-member
        except sh.ErrorReturnCode_5:
            raise KeyError(name)

    def clone_repository(self, url, path, recurse=True, ref=None):
        args = ['clone']
        if recurse:
            args.append('--recurse-submodules')

        args.extend((url, path))
        self.git(*args)

        if ref is not None:
            self.git('-C', path, 'checkout', ref)
