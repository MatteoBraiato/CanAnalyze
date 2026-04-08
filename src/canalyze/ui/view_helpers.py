from __future__ import annotations

from collections.abc import Callable
from typing import Any


def materialize_filtered_rows(
    table_rows_provider: Callable[[], list[dict[str, Any]]],
    filtered_indices: list[int],
) -> list[dict[str, Any]]:
    table_rows = table_rows_provider()
    return [table_rows[index] for index in filtered_indices]
