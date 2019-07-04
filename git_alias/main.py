import contextlib
from enum import Enum
import logging
import pathlib
import tempfile

import sh
import click

LOG = logging.getLogger(__name__)


class Config:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        return repr(self.__dict__)

    def __str__(self):
        return str(self.__dict__)


class Target(Enum):
    '''Constants that correspond to git config's --system, --global,
    --local, and --worktree command line options.'''
    SYSTEM = 1
    GLOBAL = 2
    LOCAL = 3
    WORKTREE = 4


@contextlib.contextmanager
def Directory(changedir=None, repository=None):
    cleanup = False
    path = '.'

    if changedir is not None:
        path = changedir
    elif repository is not None:
        cleanup = True
        path = tempfile.mkdtemp(prefix='alias')

    yield path

    # pylint: disable=no-member
    if cleanup:
        sh.rm('-rf', path)


class AliasCommand(click.Command):
    def __init__(self, *args, aliases=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.aliases = set(aliases) if aliases else set()


class AliasGroup(click.Group):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.aliases = {}

    def get_command(self, ctx, name):
        res = super().get_command(ctx, name)
        if res:
            return res

        return self.aliases.get(name)

    def add_command(self, cmd, name=None):
        super().add_command(cmd, name=name)

        aliases = getattr(cmd, 'aliases', [])
        for alias in aliases:
            self.aliases[alias] = cmd


@click.command(cls=AliasGroup,
               context_settings=dict(auto_envvar_prefix='GIT_ALIAS'))
@click.option('-s', '--system', 'target',
              is_flag=True,
              flag_value=Target.SYSTEM,
              help='Manage aliases in system configuration (/etc/gitconfig)')
@click.option('-g', '--global', 'target',
              is_flag=True,
              flag_value=Target.GLOBAL,
              help='Manage aliases in global configuration (~/.gitconfig)')
@click.option('-l', '--local', 'target',
              is_flag=True,
              flag_value=Target.LOCAL,
              help='Manage aliases in local configuration (.git/config)')
@click.option('-w', '--worktree', 'target',
              is_flag=True,
              flag_value=Target.WORKTREE,
              help='Manage aliases in worktree configuration (.git/config.worktree)')  # noqa
@click.option('-f', '--file', 'target',
              default=Target.GLOBAL,
              help='Manage aliases in the named file')
@click.option('-v', '--verbose', type=int, count=True)
@click.pass_context
def main(ctx, target, verbose):
    LOG.debug('using target %s', target)
    ctx.obj = Config(target=target)
    ctx.obj.git = sh.git.bake('--no-pager')

    try:
        loglevel = ['WARNING', 'INFO', 'DEBUG'][verbose]
    except IndexError:
        loglevel = 'DEBUG'

    logging.basicConfig(
        level=loglevel
    )

    # suppress logging from sh module unless we are logging
    # debug messages
    if loglevel != 'DEBUG':
        sh_logger = logging.getLogger('sh')
        sh_logger.setLevel('WARNING')

    args = []
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

    ctx.obj.conf = sh.git.bake('--no-pager', 'config', *args)


@main.command(name='add')
@click.option('-R', '--repository')
@click.option('-r', '--ref')
@click.option('-C', '--changedir')
@click.option('-n', '--name')
@click.argument('alias')
@click.pass_context
def alias_add(ctx, repository, ref, changedir, name, alias):
    ctx = ctx.obj

    with Directory(changedir=changedir, repository=repository) as path:
        alias = pathlib.Path(path) / alias

        if repository:
            LOG.info('cloning %s', repository)
            ctx.git('clone', repository, path)
            if ref:
                LOG.info('checking out %s', ref)
                ctx.git('-C', path, 'checkout', ref)

        with alias.open() as fd:
            content = []
            for line in fd:
                if not line.strip():
                    continue
                if line.startswith('#'):
                    continue
                content.append(line.strip())

            content = ' '.join(content)

    if name is None:
        if alias.name.endswith('.alias'):
            name = alias.name[:-6]
        else:
            name = alias.name

    LOG.info('installing alias %s from %s', name, alias)
    ctx.conf('alias.{}'.format(name), content)


@main.command(cls=AliasCommand, name='list', aliases=['ls'])
@click.pass_context
def alias_list(ctx):
    ctx = ctx.obj

    list_res = ctx.conf('--list', '--name-only')
    for line in list_res.stdout.decode().splitlines():
        path = line.split('.')
        if path[0] != 'alias':
            continue

        alias_name = '.'.join(path[1:])
        print(alias_name)


@main.command(cls=AliasCommand, name='show', aliases=['cat'])
@click.argument('alias')
@click.pass_context
def alias_show(ctx, alias):
    ctx = ctx.obj
    res = ctx.conf('--get', 'alias.{}'.format(alias))
    print(res.stdout.decode())


@main.command(cls=AliasCommand, name='remove', aliases=['rm'])
@click.argument('alias')
@click.pass_context
def alias_remove(ctx, alias):
    ctx = ctx.obj
    LOG.info('removing alias %s', alias)
    try:
        ctx.conf('--unset', 'alias.{}'.format(alias))
    # pylint: disable=no-member
    except sh.ErrorReturnCode_5:
        LOG.warning('failed to remove alias %s (does not exist)', alias)
