"""Importing the package registers every method; nothing else may import these directly."""

from app.analysis.methods import constant_pool, regime_score  # noqa: F401

__all__ = ["constant_pool", "regime_score"]
