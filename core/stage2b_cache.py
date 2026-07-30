"""Integrity contract for Stage 2B canonical training caches."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CanonicalCacheKey:
    sample_id: str
    trunk_checkpoint_sha256: str
    manifest_sha256: str
    score_index_sha256: str
    decoder_sha256: str
    mask_token_id: str
    preprocessing_version: str
    ridge_lambda: float
    dtype_policy: str

    def __post_init__(self) -> None:
        text_fields = (
            "sample_id",
            "trunk_checkpoint_sha256",
            "manifest_sha256",
            "score_index_sha256",
            "decoder_sha256",
            "mask_token_id",
            "preprocessing_version",
            "dtype_policy",
        )
        for name in text_fields:
            if not str(getattr(self, name)):
                raise ValueError(f"canonical cache key field {name} is empty")
        for name in (
            "trunk_checkpoint_sha256",
            "manifest_sha256",
            "score_index_sha256",
            "decoder_sha256",
        ):
            value = str(getattr(self, name))
            if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise ValueError(f"canonical cache key field {name} is not SHA256")
        if self.ridge_lambda < 0:
            raise ValueError("ridge lambda must be nonnegative")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def sha256(self) -> str:
        payload = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def assert_cache_key(
    observed: dict[str, Any], expected: CanonicalCacheKey
) -> None:
    """Abort on any stale, missing, or extra cache-key field."""

    expected_value = expected.to_dict()
    if observed != expected_value:
        missing = sorted(set(expected_value) - set(observed))
        extra = sorted(set(observed) - set(expected_value))
        changed = sorted(
            key
            for key in set(observed) & set(expected_value)
            if observed[key] != expected_value[key]
        )
        raise ValueError(
            "canonical cache key mismatch "
            f"(missing={missing}, extra={extra}, changed={changed})"
        )
