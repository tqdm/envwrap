import os

import pytest


@pytest.fixture(autouse=True)
def set_env():
    os.environ["FOO_A"] = "42"
    os.environ["FOO_C"] = "1337"


def test_envwrap():
    from envwrap import envwrap

    @envwrap("FOO")
    def test(a=1, b=2, c=3):
        return {"a": a, "b": b, "c": c}

    assert test(c=99) == {"a": 42, "b": 2, "c": 99}
