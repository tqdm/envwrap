"""Override parameter defaults via environment variables & config files."""
import logging
import os
from functools import partial, partialmethod

try:
    from functools import cache  # py>=3.9
except ImportError:
    from functools import lru_cache
    cache = lru_cache(maxsize=None)
from inspect import signature
from pathlib import Path, PurePath
from warnings import warn

from platformdirs import PlatformDirs

log = logging.getLogger(__name__)


def read_config(fpath: PurePath) -> dict:
    log.debug("Reading: %s", fpath)
    ext = fpath.suffix.lower()[1:]
    if ext == 'toml':
        try:
            from tomllib import loads  # py>=3.11
        except ModuleNotFoundError:
            from toml import loads
    elif ext in ('yaml', 'yml'):
        from yaml import safe_load as loads
    elif ext == 'json':
        from json import loads
    elif ext in ('ini', 'cfg'):
        from configparser import ConfigParser
        parser = ConfigParser()
        parser.read_string(fpath.read_text())
        res = {sec: dict(parser.items(sec)) for sec in parser.sections() if sec.count('.') == 0}
        for sec in parser.sections():
            if sec.count('.') == 1:
                parent, child = sec.split('.', 1)
                res.setdefault(parent, {}).setdefault(child, {})
                res[parent][child] |= parser.items(sec)
            elif sec.count('.') > 1:
                warn(f"Skipping nested section: {sec}", UserWarning, stacklevel=2)
        return res
    else:
        raise TypeError(f"Unsupported config filetype: {fpath}")

    return loads(fpath.read_text())


@cache
def get_defaults(name: str, app: str, func: str):
    """In-memory (functools.cache) of overrides extracted from config files & env vars."""
    conf = PlatformDirs(name, False)
    overrides = {}
    for pth, base in (
        (conf.site_config_path, name),
        (conf.site_config_path, app),
        (conf.user_config_path, name),
        (conf.user_config_path, app),
        (Path("."), name),
    ):
        if not base:
            continue
        log.debug("Searching in %s/%s.*", pth, base)
        for ext in ('cfg', 'ini', 'json', 'yml', 'yaml', 'toml'):
            if (fpath := pth / f"{base}.{ext}").is_file():
                try:
                    cfg = read_config(fpath)
                    overrides.update(cfg)
                    if base == name:
                        # app.func.a,func.a,app.a,a
                        if app in cfg:
                            overrides.update(cfg[app])
                        if func in cfg:
                            overrides.update(cfg[func])
                        if app in cfg and func in cfg[app]:
                            overrides.update(cfg[app][func])
                    elif base == app:
                        # func.a,a
                        if func in cfg:
                            overrides.update(cfg[func])
                except Exception as exc:
                    log.debug(f"Exception ignored: {exc}")
    if app:
        prefixes = name, f"{name}_{app}", f"{name}_{func}", f"{name}_{app}_{func}"
    else:
        prefixes = name, f"{name}_{func}"
    for prefix in prefixes:
        prefix = prefix.upper() + "_"
        log.debug(f"Looking for variables: {prefix}*")
        overrides.update(
            (k[len(prefix):].lower(), v) for k, v in os.environ.items() if k.startswith(prefix))
    return overrides


def envwrap(name: str, app: str = "", types: dict = None, is_method=False):
    """Function decorator overriding default arguments.

    Precedence (descending):
    - call (`func(a=3)`)
    - environment (`NAME_APP_FUNC_A=2`, `NAME_FUNC_A=2`, `NAME_APP_A=2`, `NAME_A=2`)
        - `UPPER_CASE` env vars -> `lower_case` param names
        - other cases aren't supported because Windows ignores case
    - config file:
        - ./`{name}.{toml,yaml,yml,json,ini,cfg}::{app.func.a,func.a,app.a,a}`
        - platformdirs.{user,site}_config_path(name, False)/
            - `{app}.{toml,yaml,yml,json,ini,cfg}::{func.a,a}`
            - `{name}.{toml,yaml,yml,json,ini,cfg}::{app.func.a,func.a,app.a,a}`
    - signature (`def foo(a=1)`)

    Parameters
    ----------
    name:
        Configuration name.
    app:
        Application name.
    types:
        Fallback mappings `{'param_name': type, ...}` if types cannot be
        inferred from function signature.
        Consider using `types=collections.defaultdict(lambda: ast.literal_eval)`.
    is_method:
        Whether to use `functools.partialmethod`. If (default: False) use `functools.partial`.

    Examples
    --------
    >>> os.environ.update(dict(FOO_A="7", FOO_TEST_A="42", FOO_C="1337"))
    >>> from envwrap import envwrap
    >>> @envwrap("FOO")
    >>> def test(a=1, b=2, c=3):
    ...     print(f"received: a={a}, b={b}, c={c}")
    ...
    >>> test(c=99)
    received: a=42, b=2, c=99

    """
    if types is None:
        types = {}
    if name[-1] == "_":
        name = name[:-1]
        warn("Trailing underscore in `name` is automatic", DeprecationWarning, stacklevel=2)

    part = partialmethod if is_method else partial

    def wrap(func):
        params = signature(func).parameters
        env_overrides = get_defaults(name, app, func.__name__)
        # ignore unknown env vars
        overrides = {k: v for k, v in env_overrides.items() if k in params}
        log.debug("Loaded overrides for %s: %s", func.__name__, overrides)
        # infer overrides' `type`s
        for k in overrides:
            param = params[k]
            if param.annotation is not param.empty: # typehints
                for typ in getattr(param.annotation, '__args__', (param.annotation,)):
                    try:
                        overrides[k] = typ(overrides[k])
                    except Exception:
                        log.debug("Failed to convert %s to %s", overrides[k], typ)
                    else:
                        break
            elif param.default is not None:         # type of default value
                overrides[k] = type(param.default)(overrides[k])
            else:
                try:                                # `types` fallback
                    overrides[k] = types[k](overrides[k])
                except KeyError:                    # keep unconverted (`str`)
                    pass
        log.debug("Typed overrides: %s", overrides)
        return part(func, **overrides)

    return wrap
