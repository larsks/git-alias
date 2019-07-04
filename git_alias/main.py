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


class source_flags(Enum):
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

    if cleanup:
        sh.rm('-rf', path)


@click.group()
@click.option('-s', '--system', 'src', is_flag=True, flag_value=source_flags.SYSTEM)
@click.option('-g', '--global', 'src', is_flag=True, flag_value=source_flags.GLOBAL)
@click.option('--local', 'src', is_flag=True, flag_value=source_flags.LOCAL,
              default=True)
@click.option('-w', '--worktree', 'src', is_flag=True,
              flag_value=source_flags.WORKTREE)
@click.option('-f', '--file', 'src', default=source_flags.LOCAL)
@click.option('-v', '--verbose', count=True)
@click.pass_context
def main(ctx, src, verbose):
    ctx.obj = Config(src=src)
    ctx.obj.git = sh.git.bake('--no-pager')

    loglevel = ['WARNING', 'INFO', 'DEBUG'][verbose]
    logging.basicConfig(
        level=loglevel
    )

    # suppress logging from sh module unless we are logging
    # debug messages
    if loglevel != 'DEBUG':
        sh_logger = logging.getLogger('sh')
        sh_logger.setLevel('WARNING')

    args = []
    if src is source_flags.SYSTEM:
        args.append('--system')
    elif src is source_flags.GLOBAL:
        args.append('--global')
    elif src is source_flags.LOCAL:
        args.append('--local')
    elif src is source_flags.WORKTREE:
        args.append('--worktree')
    else:
        args.extend(('--file', src))

    ctx.obj.conf = sh.git.bake('--no-pager', 'config', *args)


@main.command()
@click.option('-R', '--repository')
@click.option('-C', '--changedir')
@click.option('-n', '--name')
@click.argument('alias')
@click.pass_context
def add(ctx, repository, changedir, name, alias):
    ctx = ctx.obj

    with Directory(changedir=changedir, repository=repository) as path:
        alias = pathlib.Path(path) / alias

        if repository:
            ctx.git('clone', repository, path)

        with alias.open() as fd:
            content = fd.read()

    if name is None:
        if alias.name.endswith('.alias'):
            name = alias.name[:-6]
        else:
            name = alias.name

    LOG.info('installing alias %s from %s', name, alias)
    ctx.conf('alias.{}'.format(name), content)



@main.command()
@click.pass_context
def list(ctx):
    ctx = ctx.obj

    src = ctx.src

    list_res = ctx.conf('--list', '--name-only')
    for line in list_res.stdout.decode().splitlines():
        path = line.split('.')
        if path[0] != 'alias':
            continue

        alias_name = '.'.join(path[1:])
        print(alias_name)


@main.command()
@click.argument('alias')
@click.pass_context
def show(ctx, alias):
    ctx = ctx.obj
    res = ctx.conf('--get', 'alias.{}'.format(alias))
    print(res.stdout.decode())

@main.command()
@click.argument('alias')
@click.pass_context
def remove(ctx, alias):
    ctx = ctx.obj
    LOG.info('removing alias %s', alias)
    try:
        ctx.conf('--unset', 'alias.{}'.format(alias))
    except sh.ErrorReturnCode_5:
        LOG.warning('failed to remove alias %s (does not exist)', alias)

