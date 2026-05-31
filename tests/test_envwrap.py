import os
from textwrap import dedent

import pytest

from envwrap import envwrap


@pytest.fixture(autouse=True)
def set_env():
    os.environ["ENVWRAP_B"] = "42"
    os.environ["ENVWRAP_C"] = "1337"
    os.environ["ENVWRAP_TESTENV_D"] = "360"
    os.environ["ENVWRAP_FUNCNAME_E"] = "101"
    os.environ["ENVWRAP_TESTENV_FUNCNAME_F"] = "404"


def funcname(a=1, b=2, c=3, d=4, e=5, f=6):
    return {"a": a, "b": b, "c": c, "d": d, "e": e, "f": f}


def test_env():
    f = envwrap("envwrap", "testenv")(funcname)
    assert f(c=99) == {"a": 1, "b": 42, "c": 99, "d": 360, "e": 101, "f": 404}


def test_conf(tmp_path):
    cfg = tmp_path / "cfgwrap.toml"
    cfg.write_text(
        dedent("""
        [testcfg]
        b = 43
        c = 1338
        d = 361
        [funcname]
        e = 102
        [testcfg.funcname]
        f = 405
        """))
    pwd = os.curdir
    os.chdir(tmp_path)
    try:
        f = envwrap("cfgwrap", "testcfg")(funcname)
        assert f(c=98) == {"a": 1, "b": 43, "c": 98, "d": 361, "e": 102, "f": 405}
    finally:
        os.chdir(pwd)
        cfg.unlink()
        tmp_path.rmdir()
