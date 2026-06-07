# envwrap

[![CI](https://github.com/tqdm/envwrap/actions/workflows/test.yml/badge.svg)](https://github.com/tqdm/envwrap/actions/workflows/test.yml)
[![coveralls](https://img.shields.io/coveralls/github/tqdm/envwrap/main?logo=coveralls)](https://coveralls.io/github/tqdm/envwrap)
[![codecov](https://codecov.io/gh/tqdm/envwrap/graph/badge.svg?token=PEWICBIPVW)](https://codecov.io/gh/tqdm/envwrap)
[![codacy](https://app.codacy.com/project/badge/Grade/6ca7a441560444489fd5c5b1548ab0de)](https://app.codacy.com/gh/tqdm/envwrap/dashboard)

[![releases](https://img.shields.io/pypi/v/envwrap.svg?label=changelog)](https://github.com/tqdm/envwrap/releases)
[![pypi/envwrap](https://img.shields.io/pypi/pyversions/envwrap.svg?logo=python&logoColor=white)](https://pypi.org/project/envwrap)
[![conda-forge::envwrap](https://img.shields.io/conda/v/conda-forge/envwrap.svg?label=conda-forge&logo=conda-forge)](https://anaconda.org/conda-forge/envwrap)

Override parameter defaults via environment variables & config files.

```py
import envwrap

@envwrap.envwrap("name", "app")
def func(a=1):
    ...
```

Precedence (descending):

- call (`func(a=3)`)
- environment (`NAME_APP_FUNC_A=2`, `NAME_FUNC_A=2`, `NAME_APP_A=2`, `NAME_A=2`)
  - `UPPER_CASE` env vars -> `lower_case` param names
  - other cases aren't supported because Windows ignores case
- config file:
  - ./`{name}.{toml,yaml,yml,json,ini,cfg}::{app.func.a,func.a,app.a,a}`
  - [platformdirs](https://platformdirs.readthedocs.io/en/latest/parameters.html).{user,site}_config_path(name, False)/
    - `{app}.{toml,yaml,yml,json,ini,cfg}::{func.a,a}`
    - `{name}.{toml,yaml,yml,json,ini,cfg}::{app.func.a,func.a,app.a,a}`
  - ./`pyproject.toml::tool.name.{app.func.a,func.a,app.a,a}`
- signature (`def foo(a=1)`)

## Installation

Any one of:

- `pip install envwrap`
- `conda install -c conda-forge envwrap`
- `pip install "git+https://github.com/tqdm/envwrap@main"`

> [!TIP]
> Note that [`tqdm`](https://github.com/tqdm/tqdm) ships with a basic [`tqdm.utils.envwrap`](https://tqdm.github.io/docs/tqdm.utils/#envwrap), which falls back to the original env-var-only (no config file support) implementation if `import envwrap` fails.

## Advanced Usage

### CLI integration

```py
"""CLI example program using envwrap for configuration management.

Usage:
  myapp.py [options] <arg1> [<arg2>]

Options:
  -h, --help    Show this help message and exit.
  -o=<value>, --option=<value>  An option [default: foo].

Arguments:
  <arg1>         An argument.
  <arg2>         An integer argument [default: 2:int].

Defaults above may be overridden by environment variables or config files:
- `MYAPP[_CLI]_*`
- `{.,~/.config/myapp,/etc/xdg/myapp}/myapp[/cli].{toml,yml,json,ini}::[cli.]*`
- `pyproject.toml::tool.myapp[.cli]*`
"""
import argopt, shtab, envwrap

ONLY_PASS_VALID = True # trim envwrap defaults based on parser's valid actions

if __name__ == "__main__":
    parser = argopt.argopt(__doc__)
    shtab.add_argument_to(parser)

    defaults = envwrap.get_defaults("myapp", "", "cli")
    if ONLY_PASS_VALID:
        valid = {i.dest for i in parser._actions}
        defaults = {k: defaults[k] for k in defaults.keys() & valid}

    parser.set_defaults(**defaults)
    args = parser.parse_args()
    print(args)
```

### Live-reload

To force re-reading config files & environment variables without restarting the process:

```py
envwrap.get_defaults.cache_clear()
```

### Debugging

A CLI tool can print defaults. For example, with this config:

```toml
# config file: foo.toml
[test]
a = 1337
b = 2
```

```sh
python -m envwrap --help
FOO_A=42 python -m envwrap foo test
```

will print:

```py
>>> @envwrap.envwrap('foo', '')
>>> def test(...):
...    ...
will use defaults:
{'a': '42', 'b': 2, ...}
```
