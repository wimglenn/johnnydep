import json
from argparse import ArgumentTypeError
from subprocess import check_output
from subprocess import CalledProcessError

from johnnydep import env_check
from johnnydep.compat import JSONDecodeError


def python_interpreter(path):
    try:
        env_json = check_output([path, env_check.__file__])
    except CalledProcessError:
        raise ArgumentTypeError("Invalid python env call")
    try:
        env = json.loads(env_json.decode())
    except JSONDecodeError:
        raise ArgumentTypeError("Invalid python env output")
    frozen = tuple(map(tuple, env))
    return frozen
