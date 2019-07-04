# git-alias: manage your Git aliases

`git-alias` is a tool for managing your git aliases.

## Install

To install a released version of `git-alias`:

```
pip install git-alias
```

Or to install straight from GitHub:

```
pip install git+https://github.com/larsks/git-alias
```

`git-alias` requires Python 3.7 or later.

## Managing aliases

### Listing aliases

```
$ git alias list
conflicts
fix
please
pr
tracking
```

### Installing from a local file

```
$ git alias -v install examples/pr.alias
INFO:git_alias.main:installing alias pr from examples/pr.alias
```

### Installing from a git repository

```
$ git alias -v add -R https://github.com/larsks/git-alias examples/pr.alias
INFO:git_alias.main:cloning https://github.com/larsks/git-alias
INFO:git_alias.main:installing alias pr from /tmp/aliasmylwfb93/examples/pr.alias
```

### Show alias expansion

```
$ git alias show pr
!if [ $# -eq 1 ]; then set -- origin $1; elif [ $# -ne 2 ]; then echo
'Usage: git pr [<remote>] <pr>'; exit 2; fi; git fetch "${1}"
"+pull/${2}/head:pull/${1}/${2}"; git log -1 "pull/${1}/${2}" #
```

## Alias file format

Blank lines and lines beginning with `#` are discarded. The remaining content will be joined on spaces.  For example, this file:

```
# Create a local branch from a pull request
#
# usage: git pr [<remote>] <pr>
#
# Get a pull request from origin:
#
#   git pr 42
#   git pr origin 42
#
# Either of the above would create local branch pull/origin/42.
#
# Get a pull request from another remote:
#
#   git pr upstream 42

!if [ $# -eq 1 ]; then
  set -- origin $1;
elif [ $# -ne 2 ]; then
  echo 'Usage: git pr [<remote>] <pr>';
  exit 2;
fi;
git fetch "${1}" "+pull/${2}/head:pull/${1}/${2}"; git log -1 "pull/${1}/${2}" #
```

Results in the following entry in your git configuration file:

```
	pr = "!if [ $# -eq 1 ]; then set -- origin $1; elif [ $# -ne 2 ]; then echo 'Usage: git pr [<remote>] <pr>'; exit 2; fi; git fetch \"${1}\" \"+pull/${2}/head:pull/${1}/${2}\"; git log -1 \"pull/${1}/${2}\" # "
```
