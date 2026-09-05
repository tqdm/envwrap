import os
import shutil
from ast import literal_eval
from collections import defaultdict
from pathlib import Path
from textwrap import dedent
from typing import List, Optional, Union

import pytest

from envwrap import cast, cli, envwrap, get_defaults, read_config


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
def test_conf(tmp_path, monkeypatch, base, ext):
    config = {
        'testcfg': {'b': 43, 'c': 1338, 'd': 361,
                    'funcname': {'f': 405}}, 'funcname': {'e': 102, 'a': 0},
        'cfgwrap': {'b': -1, 'e': -2, 'f': -3, 'funcname': {'e': -4}}}
    write_config(tmp_path / f"{base}.{ext}", config)
    monkeypatch.chdir(tmp_path)
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


def test_pyproject(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    shutil.copy(Path(__file__).parent.parent / "pyproject.toml", "pyproject.toml")
    for tool, key in (('isort', 'line_length'), ('flake8', 'max_line_length'), ('yapf',
                                                                                'column_limit')):
        assert get_defaults(tool, '', '')[key] == 99

    assert get_defaults('coverage', '', 'report')['show_missing'] is True
    assert get_defaults('coverage', 'report', '')['show_missing'] is True
    assert get_defaults('coverage', 'report', 'show_missing')['report']['show_missing'] is True


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


def test_bool(monkeypatch):
    monkeypatch.setenv('FUNC_default_true', "False")
    monkeypatch.setenv('FUNC_default_false', "1")
    monkeypatch.setenv('FUNC_annotated', "0")
    monkeypatch.setenv('FUNC_fallback', "yes")

    @envwrap("func", types={'fallback': bool})
    def func(default_true=True, default_false=False, annotated: bool = None, fallback=None):
        return default_true, default_false, annotated, fallback

    assert (False, True, False, True) == func()


@pytest.mark.parametrize('typ,value,expect', [(bool, "Yes", True), (bool, " OFF ", False),
                                              (bool, "", False),
                                              (bool, True, True), (bool, 1, True),
                                              (None, "Null", None), (type(None), "NONE", None),
                                              (type(None), None, None), (int, "42", 42),
                                              (int, 42, 42), (str, 42, "42"), (float, "1.5", 1.5),
                                              (literal_eval, "[1, 2]", [1, 2])])
def test_cast(typ, value, expect):
    assert cast(value, typ) == expect


@pytest.mark.parametrize('typ,value', [(bool, "maybe"), (None, "42"), (type(None), 0), (int, "x"),
                                       (list, "abc"), (List[int], "1,2"), (dict, "ab")])
def test_cast_invalid(typ, value):
    with pytest.raises((TypeError, ValueError)):
        cast(value, typ)


def test_none(monkeypatch):
    for k, v in {
            'optional': "none", 'hinted': "NULL", 'default': " none ", 'fallback': "",
            'keep': "none", 'empty': ""}.items():
        monkeypatch.setenv(f"NONEWRAP_{k}", v)

    @envwrap("nonewrap", types={'fallback': Optional[int]})
    def func(optional: Optional[int] = 5, hinted: int = None, default=None, fallback=1, keep="s",
             empty="s"):
        return optional, hinted, default, fallback, keep, empty

    assert func() == (None, None, None, None, "none", "")


def test_cast_cascade(monkeypatch):
    monkeypatch.setenv('CASCADE_num', "3.7")     # annotation fails -> type of default
    monkeypatch.setenv('CASCADE_word', "seven")  # annotation fails -> type of default
    monkeypatch.setenv('CASCADE_data', "[1, 2]") # annotation & default fail -> `types`
    monkeypatch.setenv('CASCADE_unknown', "?")   # nothing works -> unconverted

    @envwrap("cascade", types={'word': int, 'data': literal_eval})
    def func(num: int = 1.5, word: int = "one", data: int = None, unknown: int = None):
        return num, word, data, unknown

    assert func() == (3.7, "seven", [1, 2], "?")


def test_types_defaultdict(monkeypatch):
    monkeypatch.setenv('DD_data', "{'a': 1}")
    monkeypatch.setenv('DD_num', "0x10")
    monkeypatch.setenv('DD_word', "seven")

    @envwrap("dd", types=defaultdict(lambda: literal_eval))
    def func(data=None, num=None, word=None):
        return data, num, word

    assert func() == ({'a': 1}, 16, "seven")


def test_union(monkeypatch):
    monkeypatch.setenv('UNIONWRAP_a', "1.5")
    monkeypatch.setenv('UNIONWRAP_b', "on")

    @envwrap("unionwrap", types={'b': Union[int, bool]})
    def func(a: Union[int, float] = None, b=None):
        return a, b

    assert func() == (1.5, True)


def test_containers(monkeypatch):
    """`str`s should be kept whole rather than split into characters."""
    monkeypatch.setenv('CONTWRAP_items', "abc")
    monkeypatch.setenv('CONTWRAP_typed', "1,2")

    @envwrap("contwrap")
    def func(items: list = None, typed: List[int] = None):
        return items, typed

    assert func() == ("abc", "1,2")


def test_no_default(monkeypatch):
    monkeypatch.setenv('REQWRAP_a', "abc")
    monkeypatch.setenv('REQWRAP_b', "2")

    @envwrap("reqwrap")
    def func(a: int, b=1):
        return a, b

    assert func() == ("abc", 2)


def test_method(monkeypatch):
    monkeypatch.setenv('METHWRAP_x', "5")

    class Klass:
        @envwrap("methwrap", is_method=True)
        def meth(self, x: int = 1):
            return x

    assert Klass().meth() == 5


@pytest.mark.parametrize('convert_config,expect', [(True, (True, 3, "5", None)),
                                                   (False, (True, 3, 5, "none"))])
def test_conf_types(tmp_path, monkeypatch, convert_config, expect):
    """Values already parsed by config readers shouldn't be mangled."""
    write_config(tmp_path / "typwrap.toml",
                 {'flag': True, 'num': 3, 'name': 5, 'nothing': "none", 'both': "1"})
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('TYPWRAP_envnum', "7") # env vars are always converted
    monkeypatch.setenv('TYPWRAP_both', "9")   # env wins over config -> converted

    @envwrap("typwrap", convert_config=convert_config)
    def func(flag=False, num: int = 0, name: str = "", nothing: Optional[int] = 1, envnum: int = 0,
             both: int = 0):
        return flag, num, name, nothing, envnum, both

    assert func() == expect + (7, 9)


def test_conf_types_ini(tmp_path, monkeypatch):
    """`ini`/`cfg` values are `str`s, so `convert_config=False` keeps them as such."""
    write_config(tmp_path / "iniwrap.ini", {'funcname': {'num': 3, 'flag': True}})
    monkeypatch.chdir(tmp_path)

    def funcname(num: int = 0, flag=False):
        return num, flag

    assert envwrap("iniwrap")(funcname)() == (3, True)
    assert envwrap("iniwrap", convert_config=False)(funcname)() == ("3", "True")


def test_cache_clear(monkeypatch):
    assert 'x' not in get_defaults('cachewrap', '', 'funcname')
    monkeypatch.setenv('CACHEWRAP_x', "1")
    assert 'x' not in get_defaults('cachewrap', '', 'funcname')
    get_defaults.cache_clear()
    assert get_defaults('cachewrap', '', 'funcname')['x'] == "1"


def test_platform_dirs(tmp_path, monkeypatch):
    """`platformdirs.{site,user}_config_path/{name,app}.*`"""
    class Dirs:
        site_config_path = tmp_path / "site"
        user_config_path = tmp_path / "user"

    monkeypatch.setattr('envwrap.PlatformDirs', lambda *_, **__: Dirs)
    write_config(Dirs.site_config_path / "dirwrap.toml", {'b': 1, 'testdir': {'c': 2}})
    write_config(Dirs.user_config_path / "testdir.json", {'d': 3, 'funcname': {'e': 4}})
    monkeypatch.chdir(tmp_path)

    defaults = get_defaults('dirwrap', 'testdir', 'funcname')
    assert {k: defaults[k] for k in "bcde"} == {'b': 1, 'c': 2, 'd': 3, 'e': 4}


def test_bad_config(tmp_path, monkeypatch):
    """Unparseable files should be ignored."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[tool.badwrap\n")
    (tmp_path / "badwrap.json").write_text("{invalid")
    assert get_defaults('badwrap', '', 'funcname') == {}


def test_read_config(tmp_path):
    (fpath := tmp_path / "unsupported.txt").write_text("")
    with pytest.raises(TypeError, match="Unsupported"):
        read_config(fpath)

    (fpath := tmp_path / "nested.ini").write_text("[a.b.c]\nd = 1\n")
    with pytest.warns(UserWarning, match="nested section"):
        assert read_config(fpath) == {}
