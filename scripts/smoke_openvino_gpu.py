#!/usr/bin/env python3
"""Minimal OpenVINO GPU smoke test: compile a tiny model and run on GPU."""
from __future__ import annotations

import sys
import time

import numpy as np
import openvino as ov
from openvino import opset8 as ops


def build_model() -> ov.Model:
    # y = relu(x @ w + b)  with static shapes so GPU compile is simple
    x = ops.parameter([1, 256], ov.Type.f32, name="x")
    w_const = ops.constant(np.random.randn(256, 128).astype(np.float32), name="w")
    b_const = ops.constant(np.random.randn(1, 128).astype(np.float32), name="b")
    mm = ops.matmul(x, w_const, False, False)
    add = ops.add(mm, b_const)
    y = ops.relu(add)
    y.get_output_tensor(0).set_names({"y"})
    return ov.Model([y], [x], "smoke_matmul_relu")


def main() -> int:
    core = ov.Core()
    devices = core.available_devices
    print("OpenVINO", ov.__version__)
    print("devices", devices)
    if "GPU" not in devices:
        print("FAIL: no GPU device")
        return 2

    model = build_model()
    print("Compiling for GPU...")
    t0 = time.perf_counter()
    compiled = core.compile_model(model, "GPU")
    t1 = time.perf_counter()
    print(f"compile_s={t1 - t0:.3f}")

    req = compiled.create_infer_request()
    x = np.random.randn(1, 256).astype(np.float32)
    t2 = time.perf_counter()
    out = req.infer({0: x})
    t3 = time.perf_counter()
    # second run after kernels warm
    out2 = req.infer({0: x})
    t4 = time.perf_counter()

    y = list(out.values())[0]
    print("output_shape", y.shape, "dtype", y.dtype)
    print(f"infer1_s={t3 - t2:.4f} infer2_s={t4 - t3:.4f}")
    print("OK: OpenVINO GPU compile+infer succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
