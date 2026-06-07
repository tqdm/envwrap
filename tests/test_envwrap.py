import os
import shutil
from pathlib import Path
from sys import version_info
from textwrap import dedent

import pytest

from envwrap import cli, envwrap, get_defaults


def write_config(fpath, cfg):
    ext = fpath.suffix.lower()[1:]
    fpath.parent.mkdir(parents=True, exist_ok=True)
    if ext == 'toml':
        from toml import dumps
    elif ext in ('yaml', 'yml'):
        from yaml import safe_dump as dumps
    elif ext == 'json':
        from json import dumps
    elif ext in ('ini', 'cfg'):
        from configparser import ConfigParser
        parser = ConfigParser()
        for sec, items in cfg.items():
            parser[sec] = {k: v for k, v in items.items() if not isinstance(v, dict)}
            for subsec, subitems in items.items():
                if isinstance(subitems, dict):
                    parser[f"{sec}.{subsec}"] = subitems
        with fpath.open('w') as fd:
            return parser.write(fd)
    else:
        raise TypeError(f"Unsupported config filetype: {fpath}")
    fpath.write_text(dumps(cfg))


@pytest.fixture(autouse=True)
def set_env():
    os.environ['ENVWRAP_B'] = "42"
    os.environ['ENVWRAP_C'] = "1337"
    os.environ['ENVWRAP_TESTENV_D'] = "360"
    os.environ['ENVWRAP_FUNCNAME_E'] = "101"
    os.environ['ENVWRAP_TESTENV_FUNCNAME_F'] = "404"
    get_defaults.cache_clear()


def funcname(a: int = None, b=2, c=3, d=4, e=5, f=6):
    return {'a': a, 'b': b, 'c': c, 'd': d, 'e': e, 'f': f}


def test_env():
    wrapped = envwrap('envwrap', 'testenv')(funcname)
    assert wrapped(c=99) == {'a': None, 'b': 42, 'c': 99, 'd': 360, 'e': 101, 'f': 404}
    wrapped = envwrap('envwrap')(funcname)
    assert wrapped(c=99) == {'a': None, 'b': 42, 'c': 99, 'd': 4, 'e': 101, 'f': 6}


@pytest.mark.parametrize('ext', ['toml', 'yaml', 'yml', 'json', 'ini', 'cfg'])
@pytest.mark.parametrize('base', ['cfgwrap', 'testcfg'])
def test_conf(tmp_path, base, ext):
    if version_info < (3, 9) and ext in ('ini', 'cfg'):
        pytest.skip("configparser dict merging requires python>=3.9")
    config = {
        'testcfg': {'b': 43, 'c': 1338, 'd': 361,
                    'funcname': {'f': 405}}, 'funcname': {'e': 102, 'a': 0},
        'cfgwrap': {'b': -1, 'e': -2, 'f': -3, 'funcname': {'e': -4}}}
    write_config(tmp_path / f"{base}.{ext}", config)
    pwd = os.curdir
    os.chdir(tmp_path)
    try:
        wrapped = envwrap('cfgwrap', 'testcfg')(funcname)
        if base == 'cfgwrap':
            assert wrapped(c=98) == {'a': 0, 'b': 43, 'c': 98, 'd': 361, 'e': 102, 'f': 405}
        else:
            assert wrapped(c=98) == {'a': None, 'b': 2, 'c': 98, 'd': 4, 'e': 5, 'f': 6}
        assert int(get_defaults(base, 'testcfg', 'funcname')['a']) == 0
        assert int(get_defaults(base, 'testcfg', 'funcname')['f']) == 405
        assert int(get_defaults(base, 'testcfg', 'miss-n/a')['d']) == 361
        assert int(get_defaults(base, 'cfgwrap', 'funcname')['b']) == -1
        assert int(get_defaults(base, 'cfgwrap', 'miss-n/a')['e']) == -2
        assert int(get_defaults(base, 'cfgwrap', 'funcname')['f']) == -3
        assert int(get_defaults(base, 'cfgwrap', 'funcname')['e']) == -4
    finally:
        os.chdir(pwd)


def test_pyproject(tmp_path):
    pwd = os.curdir
    os.chdir(tmp_path)
    try:
        shutil.copy(Path(__file__).parent.parent / "pyproject.toml", "pyproject.toml")
        for tool, key in (('isort', 'line_length'), ('flake8', 'max_line_length'),
                          ('yapf', 'column_limit')):
            assert get_defaults(tool, '', '')[key] == 99

        assert get_defaults('coverage', '', 'report')['show_missing'] is True
        assert get_defaults('coverage', 'report', '')['show_missing'] is True
        assert get_defaults('coverage', 'report', 'show_missing')['report']['show_missing'] is True
    finally:
        os.chdir(pwd)


def test_env_cli(capsys):
    cli.main(['envwrap', 'testenv', 'funcname'])
    out, err = capsys.readouterr()
    assert out == dedent("""\
    >>> @envwrap.envwrap('envwrap', 'testenv')
    >>> def funcname(...):
    ...    ...
    will use defaults:
    {'b': '42',
     'c': '1337',
     'd': '360',
     'e': '101',
     'f': '404',
     'funcname_e': '101',
     'funcname_f': '404',
     'testenv_d': '360',
     'testenv_funcname_f': '404'}
    """)
    assert not err

    cli.main(['envwrap', 'funcname'])
    out, err = capsys.readouterr()
    assert out == dedent("""\
    >>> @envwrap.envwrap('envwrap', '')
    >>> def funcname(...):
    ...    ...
    will use defaults:
    {'b': '42',
     'c': '1337',
     'e': '101',
     'funcname_e': '101',
     'testenv_d': '360',
     'testenv_funcname_f': '404'}
    """)
    assert not err

    with pytest.raises(ValueError):
        cli.main(['envwrap'])
    with pytest.raises(ValueError):
        cli.main(['envwrap', 'testenv', 'funcname', 'extra'])


def test_deprecated_underscore():
    with pytest.warns(DeprecationWarning, match="Trailing underscore"):
        envwrap('envwrap_', 'testenv')(funcname)
