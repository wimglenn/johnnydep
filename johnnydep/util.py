import subprocess
import json
from argparse import ArgumentTypeError

from johnnydep import env_check
from johnnydep.compat import JSONDecodeError


def python_interpreter(path):
    try:
        env_json = subprocess.check_output([path, env_check.__file__])
    except subprocess.CalledProcessError:
        raise ArgumentTypeError('Invalid python env')
    try:
        env = json.loads(env_json)
    except JSONDecodeError:
        raise ArgumentTypeError('Invalid python env')
    frozen = tuple(map(tuple, env))
    return frozen
