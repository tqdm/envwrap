# envwrap

[![CI](https://github.com/tqdm/envwrap/actions/workflows/test.yml/badge.svg)](https://github.com/tqdm/envwrap/actions/workflows/test.yml)
[![coveralls](https://img.shields.io/coveralls/github/tqdm/envwrap/main?logo=coveralls)](https://coveralls.io/github/tqdm/envwrap)
[![codecov](https://codecov.io/gh/tqdm/envwrap/graph/badge.svg?token=PEWICBIPVW)](https://codecov.io/gh/tqdm/envwrap)
[![codacy](https://app.codacy.com/project/badge/Grade/6ca7a441560444489fd5c5b1548ab0de)](https://app.codacy.com/gh/tqdm/envwrap/dashboard)

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
- signature (`def foo(a=1)`)

## Advanced Usage

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
