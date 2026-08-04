#!/usr/bin/env python3
"""Verify OpenVINO installation and GPU device visibility."""
from __future__ import annotations

import sys


def main() -> int:
    print("Python:", sys.version.replace("\n", " "))
    try:
        import openvino as ov
    except Exception as exc:  # noqa: BLE001
        print("FAIL: cannot import openvino:", exc)
        return 1

    print("OpenVINO version:", ov.__version__)
    core = ov.Core()
    devices = core.available_devices
    print("available_devices:", devices)

    if not devices:
        print("FAIL: no OpenVINO devices found")
        return 2

    for dev in devices:
        try:
            name = core.get_property(dev, "FULL_DEVICE_NAME")
        except Exception as exc:  # noqa: BLE001
            name = f"<error reading name: {exc}>"
        print(f"  - {dev}: {name}")

    if "GPU" not in devices:
        print("FAIL: GPU not in available_devices (OpenCL/L0 may work, but OpenVINO GPU plugin does not see iGPU)")
        return 3

    print("OK: OpenVINO sees GPU")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
