"""Emit deterministic SVD fingerprints for cross-machine comparison."""

import argparse
import hashlib
import json
import os
import platform
import sys
import time

import numpy as np
import scipy
import scipy.linalg


def digest(array):
    contiguous = np.ascontiguousarray(array)
    return hashlib.sha256(contiguous.view(np.uint8)).hexdigest()


def matrix_suite():
    rng = np.random.default_rng(123456789)
    matrices = {}
    for n in (32, 64, 96, 128):
        q1, _ = np.linalg.qr(rng.standard_normal((n, n)))
        q2, _ = np.linalg.qr(rng.standard_normal((n, n)))
        spectrum = np.geomspace(1.0, 1e-12, n)
        matrices[f"ill_conditioned_{n}"] = q1 @ np.diag(spectrum) @ q2.T
    matrices["rectangular_96x64"] = rng.standard_normal((96, 64))
    matrices["rank_deficient_128"] = matrices["ill_conditioned_128"].copy()
    matrices["rank_deficient_128"][:, -16:] = 0.0
    return matrices


def svd_case(name, matrix, backend, driver=None, repeats=3):
    times = []
    singular_values = None
    for _ in range(repeats):
        start = time.perf_counter()
        if backend == "numpy":
            singular_values = np.linalg.svd(matrix, compute_uv=False)
        else:
            singular_values = scipy.linalg.svd(
                matrix,
                compute_uv=False,
                lapack_driver=driver,
            )
        times.append(time.perf_counter() - start)

    return {
        "name": name,
        "backend": backend,
        "driver": driver,
        "shape": list(matrix.shape),
        "time_min_s": min(times),
        "time_median_s": sorted(times)[len(times) // 2],
        "singular_values_sha256": digest(singular_values.astype(np.float64)),
        "top8": [float(x) for x in singular_values[:8]],
        "tail8": [float(x) for x in singular_values[-8:]],
        "rank_cutoff_2e-3": int(np.count_nonzero(singular_values > 0.002)),
        "rank_cutoff_relative_2e-3": int(
            np.count_nonzero(singular_values > singular_values[0] * 0.002)
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    results = {
        "environment": {
            "python": sys.version,
            "python_executable": sys.executable,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "thread_env": {
                key: os.environ.get(key)
                for key in (
                    "OMP_NUM_THREADS",
                    "OPENBLAS_NUM_THREADS",
                    "VECLIB_MAXIMUM_THREADS",
                    "MKL_NUM_THREADS",
                    "NUMEXPR_NUM_THREADS",
                )
                if os.environ.get(key) is not None
            },
        },
        "cases": [],
    }
    for name, matrix in matrix_suite().items():
        results["cases"].append(svd_case(name, matrix, "numpy"))
        results["cases"].append(svd_case(name, matrix, "scipy", "gesdd"))
        results["cases"].append(svd_case(name, matrix, "scipy", "gesvd"))

    payload = json.dumps(results, indent=2)
    if args.out:
        with open(args.out, "w") as handle:
            handle.write(payload)
            handle.write("\n")
    print(payload)


if __name__ == "__main__":
    main()
