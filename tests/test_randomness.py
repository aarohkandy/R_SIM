from __future__ import annotations

import string

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from rocketsim.randomness import MAX_SEED, derive_seed, make_rng, sample_standard_normal

STREAMS = st.text(alphabet=string.ascii_letters + string.digits + "_-", min_size=1, max_size=32)


@given(seed=st.integers(min_value=0, max_value=MAX_SEED), stream=STREAMS)
def test_derived_seed_is_stable(seed: int, stream: str) -> None:
    assert derive_seed(seed, stream) == derive_seed(seed, stream)


def test_streams_are_independent() -> None:
    assert derive_seed(42, "plant") != derive_seed(42, "controller")


def test_rng_samples_are_reproducible() -> None:
    first = sample_standard_normal(1234, "imu", 8)
    second = sample_standard_normal(1234, "imu", 8)

    np.testing.assert_array_equal(first, second)


def test_rng_stream_names_change_samples() -> None:
    first = make_rng(1234, "imu").integers(0, 1000, size=8)
    second = make_rng(1234, "baro").integers(0, 1000, size=8)

    assert not np.array_equal(first, second)


@pytest.mark.parametrize("seed", [-1, MAX_SEED + 1])
def test_seed_range_is_validated(seed: int) -> None:
    with pytest.raises(ValueError, match="seed must be"):
        derive_seed(seed, "plant")


def test_seed_type_is_validated() -> None:
    with pytest.raises(TypeError, match="seed must be an integer"):
        derive_seed("1", "plant")  # type: ignore[arg-type]


def test_empty_stream_is_rejected() -> None:
    with pytest.raises(ValueError, match="stream must be non-empty"):
        derive_seed(1, "")


def test_negative_sample_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="count must be non-negative"):
        sample_standard_normal(1, "plant", -1)
