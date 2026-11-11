"""Version identifiers returned in every response (traceability)."""

from __future__ import annotations

from p14_search import __version__

PIPELINE_VERSION = __version__
# Bump when chunking rules change: passage ids depend on it.
CHUNKER_VERSION = "chunker-1"
