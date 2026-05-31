import argparse
import logging
from pprint import pprint

from . import get_defaults


def main(argv=None):
    parser = argparse.ArgumentParser(description="Print envwrap overrides")
    parser.add_argument("args", nargs="+", help="<name> [<app>] <func>")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="print debug info")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level={0: logging.INFO, 1: logging.DEBUG}.get(args.verbose, logging.NOTSET))
    match len(args.args):
        case 2:
            app = ""
        case 3:
            app = args.args[1]
        case _:
            raise ValueError("Usage: envwrap <config_name> [<app_name>] <func_name>")
    name = args.args[0]
    func = args.args[-1]
    print(f">>> @envwrap.envwrap('{name}', '{app}')", f">>> def {func}(...):", "...    ...",
          "will use defaults:", sep="\n")
    pprint(get_defaults(name, app, func))


if __name__ == "__main__":
    main()
