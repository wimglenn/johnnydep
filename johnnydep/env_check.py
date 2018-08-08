import json
import os
import platform
import sys


def format_full_version(info):
    version = "{0.major}.{0.minor}.{0.micro}".format(info)
    kind = info.releaselevel
    if kind != "final":
        version += kind[0] + str(info.serial)
    return version


# cribbed from packaging.markers to avoid a runtime dependency here
def default_environment():
    if hasattr(sys, "implementation"):
        iver = format_full_version(sys.implementation.version)
        implementation_name = sys.implementation.name
    else:
        iver = "0"
        implementation_name = ""

    return {
        "implementation_name": implementation_name,
        "implementation_version": iver,
        "os_name": os.name,
        "platform_machine": platform.machine(),
        "platform_release": platform.release(),
        "platform_system": platform.system(),
        "platform_version": platform.version(),
        "python_full_version": platform.python_version(),
        "platform_python_implementation": platform.python_implementation(),
        "python_version": platform.python_version()[:3],
        "sys_platform": sys.platform,
    }


def main():
    try:
        import pip
    except ImportError:
        raise EnvironmentError("pip installation is required")
    try:
        import wheel
    except ImportError:
        raise EnvironmentError("wheel installation is required")
    try:
        import packaging
    except ImportError:
        packaging_version = None
    else:
        packaging_version = packaging.__version__
    try:
        import setuptools
    except ImportError:
        setuptools_version = None
    else:
        setuptools_version = setuptools.__version__
    env = default_environment()
    env["python_executable"] = sys.executable
    env["pip_version"] = pip.__version__
    env["wheel_version"] = wheel.__version__
    env["packaging_version"] = packaging_version
    env["setuptools_version"] = setuptools_version
    env = sorted(env.items())
    result = json.dumps(env, indent=2)
    print(result)


if __name__ == "__main__":
    main()
