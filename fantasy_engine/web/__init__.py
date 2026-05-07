"""Flask web frontend for the procedural world map."""
from __future__ import annotations

import os


def _set_blas_thread_defaults() -> None:
	"""Keep NumPy/OpenBLAS imports from over-allocating worker threads.

	The web surface is observation-heavy, not dense linear algebra. Capping
	thread counts avoids OpenBLAS startup failures on constrained Windows
	environments while preserving explicit user overrides.
	"""
	for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
		os.environ.setdefault(name, "1")


_set_blas_thread_defaults()

from fantasy_engine.web.server import create_app

__all__ = ["create_app"]
