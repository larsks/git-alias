import contextlib
import logging
import pathlib
import tempfile

import sh
import click

import git_alias
from git_alias.git import Git
from git_alias.git import Target

LOG = logging.getLogger(__name__)


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

    def get_command(self, ctx, cmd_name):
        res = super().get_command(ctx, cmd_name)
        if res:
            return res

        return self.aliases.get(cmd_name)

    def add_command(self, cmd, name=None):
        super().add_command(cmd, name=name)

        aliases = getattr(cmd, 'aliases', [])
        for alias in aliases:
            self.aliases[alias] = cmd


@click.command(cls=AliasGroup,
               context_settings=dict(auto_envvar_prefix='GIT_ALIAS'))
@click.version_option(version=git_alias.__version__)
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
    ctx.obj = Git(target)

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


@main.command(name='add')
@click.option('-R', '--repository')
@click.option('-r', '--ref')
@click.option('-C', '--changedir')
@click.option('-n', '--name')
@click.argument('alias')
@click.pass_context
def alias_add(ctx, repository, ref, changedir, name, alias):
    api = ctx.obj

    with Directory(changedir=changedir, repository=repository) as path:
        alias = pathlib.Path(path) / alias

        if repository:
            LOG.info('cloning %s', repository)
            api.clone_repository(repository, path, ref=ref)

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
    api.set_alias(name, content)


@main.command(cls=AliasCommand, name='list', aliases=['ls'])
@click.pass_context
def alias_list(ctx):
    api = ctx.obj

    for alias in api.list_aliases():
        print(alias)


@main.command(cls=AliasCommand, name='show', aliases=['cat'])
@click.option('-o', '--output-file', type=click.File(mode='w'))
@click.argument('alias')
@click.pass_context
def alias_show(ctx, output_file, alias):
    api = ctx.obj
    LOG.info('writing alias %s to file %s', alias,
             output_file.name if output_file else '<stdout>')
    print(api.get_alias(alias), file=output_file)


@main.command(cls=AliasCommand, name='remove', aliases=['rm'])
@click.argument('alias')
@click.pass_context
def alias_remove(ctx, alias):
    api = ctx.obj
    LOG.info('removing alias %s', alias)
    try:
        api.remove_alias(alias)
    except KeyError:
        raise click.ClickException('alias {} does not exist'.format(alias))


@main.command(name='export')
@click.option('-o', '--output-dir', default='.', type=pathlib.Path)
@click.argument('aliases', nargs=-1)
@click.pass_context
def alias_export(ctx, output_dir, aliases):
    api = ctx.obj
    for alias in api.list_aliases():
        if not aliases or alias in aliases:
            aliasfile = output_dir / '{}.alias'.format(alias)
            with aliasfile.open('w') as fd:
                LOG.info('writing alias %s to file %s', alias, aliasfile)
                fd.write(api.get_alias(alias))
                fd.write('\n')
