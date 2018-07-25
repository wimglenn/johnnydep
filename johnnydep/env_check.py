import json
import sys


def main():
    try:
        import pip
    except ImportError:
        raise EnvironmentError("pip installation is required")
    if int(pip.__version__.split('.')[0]) < 9:
        raise EnvironmentError("pip installation is too old, >= 9.0.0 required")
    try:
        import wheel
    except ImportError:
        raise EnvironmentError("wheel installation is required")
    if tuple(map(int, wheel.__version__.split('.'))) < (0, 31, 1):
        raise EnvironmentError("wheel installation is too old, >= 0.31.1 required")
    try:
        from packaging.markers import default_environment
    except ImportError:
        raise EnvironmentError("a recent installation of packaging is required")
    env = default_environment()
    env['python_executable'] = sys.executable
    env = sorted(env.items())
    result = json.dumps(env, indent=2)
    print(result)


if __name__ == "__main__":
    main()
