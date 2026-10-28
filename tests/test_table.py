"""Normalisation into Arrow tables."""

from __future__ import annotations

import pyarrow as pa
import pytest

from arrowlane.table import estimate_bytes, schema_digest, to_table


def test_table_passthrough() -> None:
    table = pa.table({"a": [1]})
    assert to_table(table) is table


def test_list_of_dicts() -> None:
    table = to_table([{"a": 1, "b": "x"}, {"a": 2, "b": None}])
    assert table.num_rows == 2
    assert table.column_names == ["a", "b"]


def test_dict_of_lists() -> None:
    table = to_table({"a": [1, 2], "b": ["x", "y"]})
    assert table.num_rows == 2


def test_pandas_has_no_index_column() -> None:
    pandas = pytest.importorskip("pandas")
    frame = pandas.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    table = to_table(frame)
    assert table.column_names == ["a", "b"]


def test_polars_via_arrow_c_stream() -> None:
    pytest.importorskip("polars")
    import polars

    frame = polars.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    table = to_table(frame)
    assert table.num_rows == 2
    assert table.column_names == ["a", "b"]


def test_digest_ignores_data_but_not_type() -> None:
    one = pa.table({"a": [1, 2, 3]})
    two = pa.table({"a": [9]})
    three = pa.table({"a": [1.0, 2.0]})
    assert schema_digest(one) == schema_digest(two)
    assert schema_digest(one) != schema_digest(three)


def test_estimate_bytes() -> None:
    table = pa.table({"a": [1, 2, 3]})
    assert estimate_bytes(table) == table.nbytes


def test_rejects_unknown_object() -> None:
    with pytest.raises(TypeError):
        to_table(object())


def test_record_batch() -> None:
    batch = pa.record_batch({"a": [1, 2]})
    table = to_table(batch)
    assert table.num_rows == 2
    assert table.column_names == ["a"]
