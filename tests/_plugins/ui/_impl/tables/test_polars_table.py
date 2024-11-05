from __future__ import annotations

import datetime
import json
import unittest
from typing import Any

import narwhals.stable.v1 as nw
import pytest

from marimo._data.models import ColumnSummary
from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.format import FormatMapping
from marimo._plugins.ui._impl.tables.polars_table import (
    PolarsTableManagerFactory,
)
from marimo._plugins.ui._impl.tables.table_manager import TableManager
from tests.mocks import snapshotter

HAS_DEPS = DependencyManager.polars.has()

snapshot = snapshotter(__file__)


def assert_frame_equal(a: Any, b: Any) -> bool:
    import polars.testing

    if isinstance(a, nw.DataFrame):
        a = a.to_native()
    if isinstance(b, nw.DataFrame):
        b = b.to_native()
    polars.testing.assert_frame_equal(a, b)
    return True


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
class TestPolarsTableManagerFactory(unittest.TestCase):
    def get_complex_data(self) -> TableManager[Any]:
        import polars as pl

        complex_data = pl.DataFrame(
            {
                "strings": ["a", "b", "c"],
                "bool": [True, False, True],
                "int": [1, 2, 3],
                "float": [1.0, 2.0, 3.0],
                "datetime": [
                    datetime.datetime(2021, 1, 1),
                    datetime.datetime(2021, 1, 2),
                    datetime.datetime(2021, 1, 3),
                ],
                "date": [
                    datetime.date(2021, 1, 1),
                    datetime.date(2021, 1, 2),
                    datetime.date(2021, 1, 3),
                ],
                "struct": [
                    {"a": 1, "b": 2},
                    {"a": 3, "b": 4},
                    {"a": 5, "b": 6},
                ],
                "list": pl.Series(
                    [[1, 2], [3, 4], [5, 6]], dtype=pl.List(pl.Int64)
                ),
                "array": pl.Series(
                    [[1], [2], [3]], dtype=pl.Array(pl.Int64, 1)
                ),
                "nulls": pl.Series([None, "data", None]),
                "category": pl.Series(
                    ["cat", "dog", "mouse"], dtype=pl.Categorical
                ),
                "set": [set([1, 2]), set([3, 4]), set([5, 6])],
                "imaginary": [1 + 2j, 3 + 4j, 5 + 6j],
                "time": [
                    datetime.time(12, 30),
                    datetime.time(13, 45),
                    datetime.time(14, 15),
                ],
                "duration": [
                    datetime.timedelta(days=1),
                    datetime.timedelta(days=2),
                    datetime.timedelta(days=3),
                ],
                "mixed_list": [
                    [1, "two"],
                    [3.0, False],
                    [None, datetime.datetime(2021, 1, 1)],
                ],
            },
            strict=False,
        )

        return self.factory.create()(complex_data)

    def setUp(self) -> None:
        import polars as pl

        self.factory = PolarsTableManagerFactory()
        self.data = pl.DataFrame(
            {
                # Integer
                "A": [1, 2, 3],
                # String
                "B": ["a", "b", "c"],
                # Float
                "C": [1.0, 2.0, 3.0],
                # Boolean
                "D": [True, False, True],
                # DateTime
                "E": [
                    datetime.datetime(2021, 1, 1),
                    datetime.datetime(2021, 1, 2),
                    datetime.datetime(2021, 1, 3),
                ],
            }
        )
        self.manager = self.factory.create()(self.data)

    def test_package_name(self) -> None:
        assert self.factory.package_name() == "polars"

    def test_to_csv(self) -> None:
        assert isinstance(self.manager.to_csv(), bytes)

    def test_to_csv_complex(self) -> None:
        complex_data = self.get_complex_data()
        data = complex_data.to_csv()
        assert isinstance(data, bytes)
        snapshot("polars.csv", data.decode("utf-8"))

    def test_to_csv_array(self) -> None:
        import numpy as np
        import polars as pl

        df = pl.DataFrame(
            {"a": [np.arange(5) for _ in range(10)]},
            schema={"a": pl.Array(pl.Int64, 5)},
        )
        manager = self.factory.create()(df)
        assert isinstance(manager.to_csv(), bytes)

    def test_to_json(self) -> None:
        assert isinstance(self.manager.to_json(), bytes)

    def test_to_json_complex(self) -> None:
        complex_data = self.get_complex_data()
        # pl.Time and pl.Object are not supported in JSON
        other_columns = [
            col
            for col in complex_data.get_column_names()
            if col
            not in [
                "time",
                "set",
                "imaginary",
            ]
        ]
        manager = complex_data.select_columns(other_columns)
        data = manager.to_json()
        assert isinstance(data, bytes)
        snapshot("polars.json", data.decode("utf-8"))

    def test_complex_data_field_types(self) -> None:
        complex_data = self.get_complex_data()
        field_types = complex_data.get_field_types()
        snapshot("polars.field_types.json", json.dumps(field_types))

    def test_select_rows(self) -> None:
        indices = [0, 2]
        selected_manager = self.manager.select_rows(indices)
        assert "PolarsTableManager" in str(type(selected_manager))
        expected_data = self.data[indices]
        assert assert_frame_equal(selected_manager.data, expected_data)

    def test_select_rows_empty(self) -> None:
        selected_manager = self.manager.select_rows([])
        assert selected_manager.data.shape == (0, 5)
        assert selected_manager.data.columns == ["A", "B", "C", "D", "E"]

    def test_select_columns(self) -> None:
        columns = ["A"]
        selected_manager = self.manager.select_columns(columns)
        assert "PolarsTableManager" in str(type(selected_manager))
        expected_data = self.data.select(columns)
        assert assert_frame_equal(selected_manager.data, expected_data)

    def test_get_row_headers(self) -> None:
        expected_headers = []
        assert self.manager.get_row_headers() == expected_headers

    def test_is_type(self) -> None:
        assert self.manager.is_type(self.data)
        assert not self.manager.is_type("not a dataframe")

    def test_get_field_types(self) -> None:
        import polars as pl

        expected_field_types = {
            "A": ("integer", "i64"),
            "B": ("string", "str"),
            "C": ("number", "f64"),
            "D": ("boolean", "bool"),
            "E": ("datetime", "datetime[μs]"),
        }
        assert self.manager.get_field_types() == expected_field_types

        complex_data = pl.DataFrame(
            {
                "A": [1, 2, 3],
                "B": ["a", "b", "c"],
                "C": [1.0, 2.0, 3.0],
                "D": [True, False, True],
                "E": [1 + 2j, 3 + 4j, 5 + 6j],
                "F": [None, None, None],
                "G": [set([1, 2]), set([3, 4]), set([5, 6])],
                "H": [
                    datetime.datetime(2021, 1, 1),
                    datetime.datetime(2021, 1, 2),
                    datetime.datetime(2021, 1, 3),
                ],
                "I": [
                    "1 days",
                    "2 days",
                    "3 days",
                ],
                "J": [
                    "0-5",
                    "5-10",
                    "10-15",
                ],
                "K": [
                    datetime.date(2021, 1, 1),
                    datetime.date(2021, 1, 2),
                    datetime.date(2021, 1, 3),
                ],
                "L": [
                    datetime.time(1, 2, 3),
                    datetime.time(4, 5, 6),
                    datetime.time(7, 8, 9),
                ],
            }
        )
        expected_field_types = {
            "A": ("integer", "i64"),
            "B": ("string", "str"),
            "C": ("number", "f64"),
            "D": ("boolean", "bool"),
            "E": ("unknown", "object"),
            "F": ("unknown", "null"),
            "G": ("unknown", "object"),
            "H": ("datetime", "datetime[μs]"),
            "I": ("string", "str"),
            "J": ("string", "str"),
            "K": ("date", "date"),
            "L": ("time", "Time"),
        }
        assert (
            self.factory.create()(complex_data).get_field_types()
            == expected_field_types
        )

    def test_limit(self) -> None:
        limited_manager = self.manager.take(1, 0)
        expected_data = self.data.head(1)
        assert "PolarsTableManager" in str(type(limited_manager))
        assert assert_frame_equal(limited_manager.data, expected_data)

    def test_take(self) -> None:
        assert self.manager.take(1, 0).data["A"].to_list() == [1]
        assert self.manager.take(2, 0).data["A"].to_list() == [1, 2]
        assert self.manager.take(2, 1).data["A"].to_list() == [2, 3]
        assert self.manager.take(2, 2).data["A"].to_list() == [3]

    def test_take_zero(self) -> None:
        limited_manager = self.manager.take(0, 0)
        assert limited_manager.data.is_empty()

    def test_take_negative(self) -> None:
        with pytest.raises(ValueError):
            self.manager.take(-1, 0)

    def test_take_negative_offset(self) -> None:
        with pytest.raises(ValueError):
            self.manager.take(1, -1)

    def test_take_out_of_bounds(self) -> None:
        # Too large of page
        assert len(self.manager.take(10, 0).data) == 3
        assert len(self.data) == 3

        # Too large of page and offset
        assert self.manager.take(10, 10).data.is_empty()

    def test_summary_integer(self) -> None:
        column = "A"
        summary = self.manager.get_summary(column)
        assert summary == ColumnSummary(
            total=3,
            nulls=0,
            unique=3,
            min=1,
            max=3,
            mean=2.0,
            median=2.0,
            std=1.0,
            p5=1.0,
            p25=2.0,
            p75=3.0,
            p95=3.0,
        )

    def test_summary_string(self) -> None:
        column = "B"
        summary = self.manager.get_summary(column)
        assert summary == ColumnSummary(
            total=3,
            nulls=0,
            unique=3,
        )

    def test_summary_number(self) -> None:
        column = "C"
        summary = self.manager.get_summary(column)
        assert summary == ColumnSummary(
            total=3,
            nulls=0,
            min=1.0,
            max=3.0,
            mean=2.0,
            median=2.0,
            std=1.0,
            p5=1.0,
            p25=2.0,
            p75=3.0,
            p95=3.0,
        )

    def test_summary_boolean(self) -> None:
        column = "D"
        summary = self.manager.get_summary(column)
        assert summary == ColumnSummary(
            total=3,
            nulls=0,
            true=2,
            false=1,
        )

    def test_summary_datetime(self) -> None:
        column = "E"
        summary = self.manager.get_summary(column)
        assert summary == ColumnSummary(
            total=3,
            nulls=0,
            min=datetime.datetime(2021, 1, 1, 0, 0),
            max=datetime.datetime(2021, 1, 3, 0, 0),
            mean=datetime.datetime(2021, 1, 2, 0, 0),
            # TODO: narwhals doesn't support median
            # and polars doesn't support quantiles for dates
            # median=datetime.datetime(2021, 1, 2, 0, 0),
        )

    def test_summary_date(self) -> None:
        import polars as pl

        data = pl.DataFrame(
            {
                "A": [datetime.date(2021, 1, 1), datetime.date(2021, 1, 2)],
            }
        )
        manager = self.factory.create()(data)
        summary = manager.get_summary("A")
        assert summary == ColumnSummary(
            total=2,
            nulls=0,
            min=datetime.date(2021, 1, 1),
            max=datetime.date(2021, 1, 2),
            mean=datetime.datetime(2021, 1, 1, 12, 0),
            # TODO: narwhals doesn't support median
            # and polars doesn't support quantiles for dates
            # median=datetime.datetime(2021, 1, 1, 12, 0),
        )

    def test_summary_does_fail_on_each_column(self) -> None:
        complex_data = self.get_complex_data()
        for column in complex_data.get_column_names():
            assert complex_data.get_summary(column) is not None

    def test_sort_values(self) -> None:
        sorted_df = self.manager.sort_values("A", descending=True).data
        expected_df = self.data.sort("A", descending=True)
        assert assert_frame_equal(sorted_df, expected_df)

    def test_get_unique_column_values(self) -> None:
        column = "A"
        unique_values = self.manager.get_unique_column_values(column)
        assert unique_values == [1, 2, 3]

    def test_search(self) -> None:
        import polars as pl

        df = pl.DataFrame(
            {
                "A": [1, 2, 3],
                "B": ["foo", "bar", "baz"],
                "C": [True, False, True],
                "D": [["zz", "yyy"], [], []],
                "E": [1.1, 2.2, 3.3],
            }
        )
        manager = self.factory.create()(df)
        # Exact match
        assert manager.search("foo").get_num_rows() == 1
        # Contains
        assert manager.search("a").get_num_rows() == 2
        # Case insensitive / boolean
        assert manager.search("true").get_num_rows() == 2
        # Overmatch
        assert manager.search("food").get_num_rows() == 0
        # Int (exact match)
        assert manager.search("1").get_num_rows() == 1
        # Float (exact match)
        assert manager.search("1.1").get_num_rows() == 1
        # List (exact match)
        assert manager.search("yyy").get_num_rows() == 1
        assert manager.search("y").get_num_rows() == 0

    def test_apply_formatting_does_not_modify_original_data(self) -> None:
        original_data = self.data.clone()
        format_mapping = {
            "A": lambda x: x * 2,
            "B": lambda x: x.upper(),
        }
        assert self.manager.apply_formatting(format_mapping).data is not None
        assert_frame_equal(self.manager.data, original_data)

    def test_apply_formatting(self) -> None:
        import polars as pl

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
            "B": lambda x: x.upper(),
            "C": lambda x: f"{x:.2f}",
            "D": lambda x: not x,
            "E": lambda x: x.strftime("%Y-%m-%d"),
        }

        formatted_data = self.manager.apply_formatting(format_mapping).data
        expected_data = pl.DataFrame(
            {
                "A": [2, 4, 6],
                "B": ["A", "B", "C"],
                "C": ["1.00", "2.00", "3.00"],
                "D": [False, True, False],
                "E": ["2021-01-01", "2021-01-02", "2021-01-03"],
            }
        )
        assert_frame_equal(formatted_data, expected_data)

    def test_apply_formatting_with_empty_dataframe(self) -> None:
        import polars as pl

        empty_data = pl.DataFrame({"A": []})
        manager = self.factory.create()(empty_data)

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
        }

        formatted_data = manager.apply_formatting(format_mapping).data
        assert_frame_equal(formatted_data, empty_data)

    def test_apply_formatting_partial(self) -> None:
        import polars as pl

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
        }

        formatted_data = self.manager.apply_formatting(format_mapping).data
        expected_data = pl.DataFrame(
            {
                "A": [2, 4, 6],
                "B": ["a", "b", "c"],
                "C": [1.0, 2.0, 3.0],
                "D": [True, False, True],
                "E": [
                    datetime.datetime(2021, 1, 1),
                    datetime.datetime(2021, 1, 2),
                    datetime.datetime(2021, 1, 3),
                ],
            }
        )
        assert_frame_equal(formatted_data, expected_data)

    def test_apply_formatting_empty(self) -> None:
        format_mapping: FormatMapping = {}

        formatted_data = self.manager.apply_formatting(format_mapping).data
        assert_frame_equal(formatted_data, self.data)

    def test_apply_formatting_invalid_column(self) -> None:
        format_mapping: FormatMapping = {
            "Z": lambda x: x * 2,
        }

        formatted_data = self.manager.apply_formatting(format_mapping).data
        assert_frame_equal(formatted_data, self.data)

    def test_apply_formatting_with_nan(self) -> None:
        import polars as pl

        data_with_nan = self.data.clone()
        data_with_nan = data_with_nan.with_columns(
            pl.when(pl.col("A").is_not_null())
            .then(pl.col("A"))
            .otherwise(None)
            .alias("A")
        )
        manager_with_nan = self.factory.create()(data_with_nan)

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2 if x is not None else x,
        }

        formatted_data = manager_with_nan.apply_formatting(format_mapping).data
        expected_data = data_with_nan.clone()
        expected_data = expected_data.with_columns(
            pl.when(pl.col("A").is_not_null())
            .then(pl.col("A") * 2)
            .otherwise(None)
            .alias("A")
        )
        assert_frame_equal(formatted_data, expected_data)

    def test_apply_formatting_with_multi_index(self) -> None:
        import polars as pl

        data = pl.DataFrame(
            {
                "A": [1, 2, 3],
                "B": ["a", "b", "c"],
            }
        ).with_row_index()
        data = data.with_columns(pl.col("index").cast(pl.Utf8))

        manager = self.factory.create()(data)

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
            "B": lambda x: x.upper(),
        }

        formatted_data = manager.apply_formatting(format_mapping).data
        expected_data = pl.DataFrame(
            {
                "index": ["0", "1", "2"],
                "A": [2, 4, 6],
                "B": ["A", "B", "C"],
            }
        )
        assert_frame_equal(formatted_data, expected_data)

    def test_apply_formatting_with_categorical_data(self) -> None:
        import polars as pl

        data = pl.DataFrame(
            {
                "A": pl.Series(["a", "b", "a"]).cast(pl.Categorical),
                "B": [1, 2, 3],
            }
        )
        manager = self.factory.create()(data)

        format_mapping: FormatMapping = {
            "A": lambda x: x.upper(),
            "B": lambda x: x * 2,
        }

        formatted_data = manager.apply_formatting(format_mapping).data
        expected_data = pl.DataFrame(
            {
                "A": pl.Series(["A", "B", "A"]),
                "B": [2, 4, 6],
            }
        )
        assert_frame_equal(formatted_data, expected_data)

    def test_apply_formatting_with_datetime_index(self) -> None:
        import polars as pl

        data = pl.DataFrame(
            {
                "A": [1, 2, 3],
                "B": ["a", "b", "c"],
            }
        ).with_columns(
            pl.date_range(
                start=datetime.datetime(2021, 1, 1),
                end=datetime.datetime(2021, 1, 3),
                interval="1d",
            ).alias("index")
        )
        data = data.with_columns(pl.col("index").cast(pl.Utf8))

        manager = self.factory.create()(data)

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
            "B": lambda x: x.upper(),
        }

        formatted_data = manager.apply_formatting(format_mapping).data
        expected_data = pl.DataFrame(
            {
                "A": [2, 4, 6],
                "B": ["A", "B", "C"],
                "index": ["2021-01-01", "2021-01-02", "2021-01-03"],
            }
        )
        assert_frame_equal(formatted_data, expected_data)

    def test_apply_formatting_with_complex_data(self) -> None:
        import polars as pl

        data = pl.DataFrame(
            {
                "A": [1, 2, 3],
                "B": ["a", "b", "c"],
                "C": [1.0, 2.0, 3.0],
                "D": [True, False, True],
                "E": [
                    datetime.datetime(2021, 1, 1),
                    datetime.datetime(2021, 1, 2),
                    datetime.datetime(2021, 1, 3),
                ],
                "F": [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
                "G": [1 + 2j, 3 + 4j, 5 + 6j],
            }
        )
        manager = self.factory.create()(data)

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
            "B": lambda x: x.upper(),
            "C": lambda x: f"{x:.2f}",
            "D": lambda x: not x,
            "E": lambda x: x.strftime("%Y-%m-%d"),
            "G": abs,
        }

        formatted_data = manager.apply_formatting(format_mapping).data
        expected_data = pl.DataFrame(
            {
                "A": [2, 4, 6],
                "B": ["A", "B", "C"],
                "C": ["1.00", "2.00", "3.00"],
                "D": [False, True, False],
                "E": ["2021-01-01", "2021-01-02", "2021-01-03"],
                "F": [
                    [1, 2, 3],
                    [4, 5, 6],
                    [7, 8, 9],
                ],  # No formatting applied
                "G": [2.23606797749979, 5.0, 7.810249675906654],
            }
        )
        assert_frame_equal(formatted_data, expected_data)

    def test_empty_dataframe(self) -> None:
        import polars as pl

        empty_df = pl.DataFrame()
        empty_manager = self.factory.create()(empty_df)
        assert empty_manager.get_num_rows() == 0
        assert empty_manager.get_num_columns() == 0
        assert empty_manager.get_column_names() == []
        assert empty_manager.get_field_types() == {}

    def test_dataframe_with_all_null_column(self) -> None:
        import polars as pl

        df = pl.DataFrame({"A": [1, 2, 3], "B": [None, None, None]})
        manager = self.factory.create()(df)
        summary = manager.get_summary("B")
        assert summary.nulls == 3
        assert summary.total == 3

    def test_dataframe_with_mixed_types(self) -> None:
        import polars as pl

        df = pl.DataFrame({"A": [1, "two", 3.0, True]}, strict=False)
        manager = self.factory.create()(df)
        field_types = manager.get_field_types()
        assert field_types["A"] == ("string", "str")

    def test_search_with_regex(self) -> None:
        import polars as pl

        df = pl.DataFrame({"A": ["apple", "banana", "cherry"]})
        manager = self.factory.create()(df)
        result = manager.search("^[ab]")
        assert result.get_num_rows() == 2

    def test_sort_values_with_nulls(self) -> None:
        import polars as pl

        df = pl.DataFrame({"A": [3, 1, None, 2]})
        manager = self.factory.create()(df)
        sorted_manager = manager.sort_values("A", descending=True)
        assert sorted_manager.data["A"].to_list() == [None, 3, 2, 1]

    def test_get_field_types_with_datetime(self):
        import polars as pl

        data = pl.DataFrame(
            {
                "date_col": [
                    datetime.date(2021, 1, 1),
                    datetime.date(2021, 1, 3),
                ],
                "datetime_col": [
                    datetime.datetime(2021, 1, 1),
                    datetime.datetime(2021, 1, 3),
                ],
                "time_col": [
                    datetime.time(1, 2, 3),
                    datetime.time(4, 5, 6),
                ],
            }
        )
        manager = self.factory.create()(data)
        field_types = manager.get_field_types()

        assert field_types["date_col"] == ("date", "date")
        assert field_types["datetime_col"] == ("datetime", "datetime[μs]")
        assert field_types["time_col"] == ("time", "Time")
