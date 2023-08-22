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
        "python_version": ".".join(platform.python_version_tuple()[:2]),
        "sys_platform": sys.platform,
    }


def main():
    env = default_environment()
    env["python_executable"] = sys.executable
    env = sorted(env.items())
    result = json.dumps(env, indent=2)
    print(result)


if __name__ == "__main__":
    main()
