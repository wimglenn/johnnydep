import json
import sys


def main():
    try:
        import pip
    except ImportError:
        raise EnvironmentError("pip installation is required")
    if int(pip.__version__.split('.')[0]) < 9:
        raise EnvironmentError("pip installation is old, >= 9.0.0 required")
    try:
        import wheel
    except ImportError:
        raise EnvironmentError("wheel installation is required")
    try:
        import packaging
    except ImportError:
        raise EnvironmentError("packaging installation is required")
    try:
        from packaging.markers import default_environment
    except ImportError:
        raise EnvironmentError("packaging installation is old, >= 16.0 required")
    try:
        import setuptools
    except ImportError:
        setuptools_version = None
    else:
        setuptools_version = setuptools.__version__
    env = default_environment()
    env['python_executable'] = sys.executable
    env['pip_version'] = pip.__version__
    env['wheel_version'] = wheel.__version__
    env['packaging_version'] = packaging.__version__
    env['setuptools_version'] = setuptools_version
    env = sorted(env.items())
    result = json.dumps(env, indent=2)
    print(result)


if __name__ == "__main__":
    main()
