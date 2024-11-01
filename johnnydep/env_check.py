import json
import sys

from packaging.markers import default_environment
from packaging.tags import interpreter_name
from unearth.pep425tags import get_supported


def main():
    env = {}
    env.update(default_environment())
    env["python_executable"] = sys.executable
    env["py_ver"] = sys.version_info[0], sys.version_info[1]
    env["impl"] = interpreter_name()
    env["platforms"] = None
    env["abis"] = None
    env["supported_tags"] = ",".join(map(str, get_supported()))
    txt = json.dumps(env, indent=2, sort_keys=True)
    print(txt)


if __name__ == "__main__":
    main()
