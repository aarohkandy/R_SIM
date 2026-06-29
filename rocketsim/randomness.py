"""Deterministic seeded random helpers."""

from __future__ import annotations

from hashlib import blake2b

import numpy as np
from numpy.typing import NDArray

MAX_SEED = 2**63 - 1


def normalize_seed(seed: int) -> int:
    """Validate and normalize a master seed."""

    if not isinstance(seed, int):
        msg = "seed must be an integer"
        raise TypeError(msg)
    if seed < 0 or seed > MAX_SEED:
        msg = f"seed must be in [0, {MAX_SEED}]"
        raise ValueError(msg)
    return seed


def derive_seed(master_seed: int, stream: str) -> int:
    """Derive a stable child seed for a named stream."""

    seed = normalize_seed(master_seed)
    if not stream:
        msg = "stream must be non-empty"
        raise ValueError(msg)
    digest = blake2b(f"{seed}:{stream}".encode(), digest_size=8).digest()
    return int.from_bytes(digest, "little") & MAX_SEED


def make_rng(master_seed: int, stream: str = "default") -> np.random.Generator:
    """Return a deterministic NumPy generator for the requested stream."""

    return np.random.default_rng(derive_seed(master_seed, stream))


def sample_standard_normal(master_seed: int, stream: str, count: int) -> NDArray[np.float64]:
    """Small deterministic sampling helper used by Phase-0 tests."""

    if count < 0:
        msg = "count must be non-negative"
        raise ValueError(msg)
    return make_rng(master_seed, stream).standard_normal(count)
