"""Local retained-SVD-norm telemetry for compression diagnostics.

This is observational: it records the product of retained local Frobenius
fractions, conventionally shown as ``fid10 = log10(product)``. It does not
alter the solver's selected ranks or tensors.
"""

from __future__ import annotations

import math
import numpy as np
from scipy import linalg as scipy_linalg
from autoray import do
from autoray.autoray import backend_like
from quimb.tensor import decomp
from quimb.tensor import tensor_core


class TruncationFid10Tracker:
    """Track retained squared singular-value fractions across MPO splits."""

    def __init__(self, svd_driver="native"):
        self.log10_retained = 0.0
        self.events = 0
        self.fallbacks = 0
        self._original = None
        self.svd_driver = svd_driver

    @property
    def retained_fraction(self):
        return 10.0 ** self.log10_retained

    def install(self):
        if self._original is not None:
            return self
        # ``tensor_compress_bond`` reaches Quimb's SVD implementation after
        # QR/LQ reduction.  The old tracker ran a *second*, untruncated SVD on
        # copies to see the discarded tail; that doubles the expensive step
        # and can OOM at an unswap peak.  Instrument the SVD Quimb already
        # performs instead, immediately before its normal trim.
        self._original = tensor_core._SPLIT_FNS["svd"]
        original = self._original
        tracker = self

        def tracked_svd(x, cutoff=-1.0, cutoff_mode=4, max_bond=-1,
                        absorb=0, renorm=0, backend=None):
            # This is Quimb's ``svd_truncated`` body with one observation of
            # ``s`` before ``_trim_and_renorm_svd_result``.  It performs the
            # exact same one SVD as the uninstrumented solver.
            absorb_code = decomp._ABSORB_MAP[absorb]
            with backend_like(backend):
                try:
                    if tracker.svd_driver == "native":
                        # Preserve Quimb's exact production path. On this
                        # laptop NumPy dispatches to Apple Accelerate LAPACK.
                        U, s, VH = do(
                            "linalg.svd", x, full_matrices=False
                        )
                    else:
                        U, s, VH = scipy_linalg.svd(
                            np.asarray(x),
                            full_matrices=False,
                            check_finite=False,
                            lapack_driver="gesvd",
                        )
                except (np.linalg.LinAlgError, ValueError):
                    # Classical gesvd remains the convergence fallback.
                    U, s, VH = scipy_linalg.svd(
                        np.asarray(x, dtype=np.complex128),
                        full_matrices=False,
                        check_finite=False,
                        lapack_driver="gesvd",
                    )
                    tracker.fallbacks += 1
                full_power = float(np.vdot(np.asarray(s), np.asarray(s)).real)
                result = decomp._trim_and_renorm_svd_result(
                    U, s, VH, cutoff, cutoff_mode, max_bond, absorb_code, renorm
                )
            # The trimmed factors' shared dimension is the kept rank.
            if full_power > 0.0:
                left = result[0]
                rank = int(np.shape(left)[-1])
                kept = np.asarray(s)[:rank]
                kept_power = float(np.vdot(kept, kept).real)
                fraction = min(1.0, max(kept_power / full_power, np.finfo(float).tiny))
                tracker.log10_retained += math.log10(fraction)
            tracker.events += 1
            return result

        tensor_core._SPLIT_FNS["svd"] = tracked_svd
        return self

    def uninstall(self):
        if self._original is not None:
            tensor_core._SPLIT_FNS["svd"] = self._original
            self._original = None
