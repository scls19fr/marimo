from __future__ import annotations

import datetime
import json
import unittest
from typing import Any
from unittest.mock import Mock

import narwhals.stable.v1 as nw
import pytest

from marimo._data.models import ColumnSummary
from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.format import FormatMapping
from marimo._plugins.ui._impl.tables.pandas_table import (
    PandasTableManagerFactory,
)
from marimo._plugins.ui._impl.tables.table_manager import TableManager
from tests.mocks import snapshotter

HAS_DEPS = DependencyManager.pandas.has()

snapshot = snapshotter(__file__)


def assert_frame_equal(a: Any, b: Any) -> None:
    import pandas as pd

    if isinstance(a, nw.DataFrame):
        a = a.to_native()
    if isinstance(b, nw.DataFrame):
        b = b.to_native()
    pd.testing.assert_frame_equal(a, b)


try:
    import pandas as pd
except ImportError:
    pd = Mock()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
class TestPandasTableManager(unittest.TestCase):
    def get_complex_data(self) -> TableManager[Any]:
        import pandas as pd

        complex_data = pd.DataFrame(
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
                "list": pd.Series([[1, 2], [3, 4], [5, 6]]),
                "nulls": pd.Series([None, "data", None]),
                "category": pd.Categorical(["cat", "dog", "mouse"]),
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
        )

        return self.factory.create()(complex_data)

    def setUp(self) -> None:
        import pandas as pd

        self.factory = PandasTableManagerFactory()
        self.data = pd.DataFrame(
            {
                # Integer
                "A": [1, 2, 3],
                # String
                "B": ["a", "b", " b"],
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
                # List
                "F": [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
            }
        )
        self.manager = self.factory.create()(self.data)

    def test_package_name(self) -> None:
        assert self.factory.package_name() == "pandas"

    def test_to_csv(self) -> None:
        expected_csv = self.data.to_csv(index=False).encode("utf-8")
        assert self.manager.to_csv() == expected_csv

    def test_to_csv_complex(self) -> None:
        complex_data = self.get_complex_data()
        data = complex_data.to_csv()
        assert isinstance(data, bytes)
        snapshot("pandas.csv", data.decode("utf-8"))

    def test_to_json(self) -> None:
        expected_json = self.data.to_json(orient="records").encode("utf-8")
        assert self.manager.to_json() == expected_json

    def test_to_json_complex(self) -> None:
        complex_data = self.get_complex_data()
        data = complex_data.to_json()
        assert isinstance(data, bytes)
        snapshot("pandas.json", data.decode("utf-8"))

    def test_complex_data_field_types(self) -> None:
        complex_data = self.get_complex_data()
        field_types = complex_data.get_field_types()
        snapshot("pandas.field_types.json", json.dumps(field_types))

    def test_select_rows(self) -> None:
        indices = [0, 2]
        selected_manager = self.manager.select_rows(indices)
        expected_data = self.data.iloc[indices]
        assert_frame_equal(selected_manager.data, expected_data)

    def test_select_rows_empty(self) -> None:
        selected_manager = self.manager.select_rows([])
        assert selected_manager.data.shape == (0, 6)

    def test_select_columns(self) -> None:
        columns = ["A", "C"]
        selected_manager = self.manager.select_columns(columns)
        expected_data = self.data[columns]
        assert_frame_equal(selected_manager.data, expected_data)

    def test_get_row_headers(self) -> None:
        expected_headers = []
        assert self.manager.get_row_headers() == expected_headers

    def test_get_row_headers_date_index(self) -> None:
        data = pd.DataFrame(
            {
                "A": [1, 2, 3],
                "B": [4, 5, 6],
                "C": [7, 8, 9],
            },
            index=pd.to_datetime(["2021-01-01", "2021-06-01", "2021-09-01"]),
        )
        manager = self.factory.create()(data)
        assert manager.get_row_headers() == [""]

    def test_get_row_headers_timedelta_index(self) -> None:
        data = pd.DataFrame(
            {
                "A": [1, 2, 3],
                "B": [4, 5, 6],
                "C": [7, 8, 9],
            },
            index=pd.to_timedelta(["1 days", "2 days", "3 days"]),
        )
        manager = self.factory.create()(data)
        assert manager.get_row_headers() == [""]

    def test_get_row_headers_multi_index(self) -> None:
        data = pd.DataFrame(
            {
                "A": [1, 2, 3],
                "B": [4, 5, 6],
                "C": [7, 8, 9],
            },
            index=pd.MultiIndex.from_tuples(
                [("a", 1), ("b", 2), ("c", 3)], names=["X", "Y"]
            ),
        )
        manager = self.factory.create()(data)
        assert manager.get_row_headers() == ["X", "Y"]

    def test_is_type(self) -> None:
        assert self.manager.is_type(self.data)
        assert not self.manager.is_type("not a dataframe")

    def test_get_field_types(self) -> None:
        expected_field_types = {
            "A": ("integer", "int64"),
            "B": ("string", "object"),
            "C": ("number", "float64"),
            "D": ("boolean", "bool"),
            "E": ("datetime", "datetime64[ns]"),
            "F": ("string", "object"),
        }
        assert self.manager.get_field_types() == expected_field_types

        complex_data = pd.DataFrame(
            {
                "A": [1, 2, 3],
                "B": ["a", "b", "c"],
                "C": [1.0, 2.0, 3.0],
                "D": [True, False, True],
                "E": [1 + 2j, 3 + 4j, 5 + 6j],
                "F": [None, None, None],
                "G": [set([1, 2]), set([3, 4]), set([5, 6])],
                "H": [
                    pd.Timestamp("2021-01-01"),
                    pd.Timestamp("2021-01-02"),
                    pd.Timestamp("2021-01-03"),
                ],
                "I": [
                    pd.Timedelta("1 days"),
                    pd.Timedelta("2 days"),
                    pd.Timedelta("3 days"),
                ],
                "J": [
                    pd.Interval(left=0, right=5),
                    pd.Interval(left=5, right=10),
                    pd.Interval(left=10, right=15),
                ],
            }
        )
        expected_field_types = {
            "A": ("integer", "int64"),
            "B": ("string", "object"),
            "C": ("number", "float64"),
            "D": ("boolean", "bool"),
            "E": ("unknown", "complex128"),
            "F": ("string", "object"),
            "G": ("string", "object"),
            "H": ("datetime", "datetime64[ns]"),
            "I": ("string", "timedelta64[ns]"),
            "J": ("string", "interval[int64, right]"),
        }
        assert (
            self.factory.create()(complex_data).get_field_types()
            == expected_field_types
        )

    @pytest.mark.xfail(
        reason="Narwhals (wrapped pandas) doesn't support duplicate columns",
    )
    def test_get_fields_types_duplicate_columns(self) -> None:
        # Different types
        data = pd.DataFrame(
            {
                "A": [1, 2, 3],
                "B": ["a", "b", "c"],
            }
        )
        data = data.rename(columns={"A": "B"})
        expected_field_types = {
            "B": ("string", "object"),
        }
        assert (
            self.factory.create()(data).get_field_types()
            == expected_field_types
        )

        # Both strings
        data = pd.DataFrame(
            {
                "A": ["a", "b", "c"],
                "B": ["d", "e", "f"],
            }
        )
        data = data.rename(columns={"A": "B"})
        expected_field_types = {
            "B": ("string", "object"),
        }
        assert (
            self.factory.create()(data).get_field_types()
            == expected_field_types
        )

        # Both integers
        data = pd.DataFrame(
            {
                "A": [1, 2, 3],
                "B": [4, 5, 6],
            }
        )
        data = data.rename(columns={"A": "B"})
        expected_field_types = {
            "B": ("string", "object"),
        }
        assert (
            self.factory.create()(data).get_field_types()
            == expected_field_types
        )

    def test_limit(self) -> None:
        limit = 2
        limited_manager = self.manager.take(limit, 0)
        expected_data = self.data.head(limit)
        assert_frame_equal(limited_manager.data, expected_data)

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
        assert len(self.manager.take(10, 10).data) == 0

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
            median=2,
            std=1.0,
            true=None,
            false=None,
            p5=1,
            p25=1,
            p75=3,
            p95=3,
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
            unique=None,
            min=1.0,
            max=3.0,
            mean=2.0,
            median=2.0,
            std=1.0,
            true=None,
            false=None,
            p5=1.0,
            p25=1.0,
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

    def test_summary_date(self) -> None:
        column = "E"
        summary = self.manager.get_summary(column)

        assert summary == ColumnSummary(
            total=3,
            nulls=0,
            unique=None,
            min=pd.Timestamp("2021-01-01 00:00:00"),
            max=pd.Timestamp("2021-01-03 00:00:00"),
            mean=pd.Timestamp("2021-01-02 00:00:00"),
            median=pd.Timestamp("2021-01-02 00:00:00"),
            std=None,
            true=None,
            false=None,
            p5=pd.Timestamp("2021-01-01 00:00:00"),
            p25=pd.Timestamp("2021-01-01 00:00:00"),
            p75=pd.Timestamp("2021-01-03 00:00:00"),
            p95=pd.Timestamp("2021-01-03 00:00:00"),
        )

    def test_summary_list(self) -> None:
        column = "F"
        summary = self.manager.get_summary(column)
        assert summary == ColumnSummary(
            total=3,
            nulls=0,
        )

    def test_summary_does_fail_on_each_column(self) -> None:
        complex_data = self.get_complex_data()
        for column in complex_data.get_column_names():
            assert complex_data.get_summary(column) is not None

    def test_sort_values(self) -> None:
        sorted_df = self.manager.sort_values("A", descending=True).data
        expected_df = self.data.sort_values("A", ascending=False)
        assert_frame_equal(sorted_df, expected_df)

    def test_sort_values_with_index(self) -> None:
        data = pd.DataFrame(
            {
                "A": [1, 3, 2],
            },
            index=[1, 3, 2],
        )
        data.index.name = "index"
        manager = self.factory.create()(data)
        sorted_df = manager.sort_values("A", descending=True).data
        assert sorted_df.to_native().index.tolist() == [3, 2, 1]

    def test_get_unique_column_values(self) -> None:
        column = "B"
        assert self.manager.get_unique_column_values(column) == [
            "a",
            "b",
            " b",
        ]

    def test_search(self) -> None:
        df = pd.DataFrame(
            {
                "A": [1, 2, 3],
                "B": ["foo", "bar", "baz"],
                "C": [True, False, True],
            }
        )
        manager = self.factory.create()(df)
        assert manager.search("foo").get_num_rows() == 1
        assert manager.search("a").get_num_rows() == 2
        assert manager.search("true").get_num_rows() == 2
        assert manager.search("food").get_num_rows() == 0

    def test_apply_formatting_does_not_modify_original_data(self) -> None:
        original_data = self.data.copy()
        format_mapping = {
            "A": lambda x: x * 2,
            "B": lambda x: x.upper(),
        }
        assert self.manager.apply_formatting(format_mapping).data is not None
        assert_frame_equal(self.manager.data, original_data)

    def test_apply_formatting(self) -> None:
        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
            "B": lambda x: x.upper(),
            "C": lambda x: f"{x:.2f}",
            "D": lambda x: not x,
            "E": lambda x: x.strftime("%Y-%m-%d"),
        }

        formatted_data = self.manager.apply_formatting(format_mapping).data
        expected_data = pd.DataFrame(
            {
                "A": [2, 4, 6],
                "B": ["A", "B", " B"],
                "C": ["1.00", "2.00", "3.00"],
                "D": [False, True, False],
                "E": ["2021-01-01", "2021-01-02", "2021-01-03"],
                "F": [
                    [1, 2, 3],
                    [4, 5, 6],
                    [7, 8, 9],
                ],  # No formatting applied
            }
        )
        assert_frame_equal(formatted_data, expected_data)

    def test_apply_formatting_with_empty_dataframe(self) -> None:
        empty_data = pd.DataFrame()
        manager = self.factory.create()(empty_data)

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
        }

        formatted_data = manager.apply_formatting(format_mapping).data
        assert_frame_equal(formatted_data, empty_data)

    def test_apply_formatting_partial(self) -> None:
        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
        }

        formatted_data = self.manager.apply_formatting(format_mapping).data
        expected_data = pd.DataFrame(
            {
                "A": [2, 4, 6],
                "B": ["a", "b", " b"],
                "C": [1.0, 2.0, 3.0],
                "D": [True, False, True],
                "E": [
                    datetime.datetime(2021, 1, 1),
                    datetime.datetime(2021, 1, 2),
                    datetime.datetime(2021, 1, 3),
                ],
                "F": [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
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
        data_with_nan = self.data.copy()
        data_with_nan.loc[1, "A"] = None
        manager_with_nan = self.factory.create()(data_with_nan)

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2 if pd.notna(x) else x,
        }

        formatted_data = manager_with_nan.apply_formatting(format_mapping).data
        expected_data = data_with_nan.copy()
        expected_data["A"] = [2, None, 6]
        assert_frame_equal(formatted_data, expected_data)

    def test_apply_formatting_with_mixed_types(self) -> None:
        data = pd.DataFrame(
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
                "G": [None, "text", 3.14],
            }
        )
        manager = self.factory.create()(data)

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
            "B": lambda x: x.upper(),
            "C": lambda x: f"{x:.2f}",
            "D": lambda x: not x,
            "E": lambda x: x.strftime("%Y-%m-%d"),
            "G": str,
        }

        formatted_data = manager.apply_formatting(format_mapping).data
        expected_data = pd.DataFrame(
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
                "G": [None, "text", "3.14"],
            }
        )
        assert_frame_equal(formatted_data, expected_data)

    def test_apply_formatting_with_multi_index(self) -> None:
        data = pd.DataFrame(
            {
                "A": [1, 2, 3],
                "B": ["a", "b", "c"],
            },
            index=pd.MultiIndex.from_tuples(
                [("x", 1), ("y", 2), ("z", 3)], names=["X", "Y"]
            ),
        )
        manager = self.factory.create()(data)

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
            "B": lambda x: x.upper(),
        }

        formatted_data = manager.apply_formatting(format_mapping).data
        expected_data = pd.DataFrame(
            {
                "A": [2, 4, 6],
                "B": ["A", "B", "C"],
            },
            index=pd.MultiIndex.from_tuples(
                [("x", 1), ("y", 2), ("z", 3)], names=["X", "Y"]
            ),
        )
        assert_frame_equal(formatted_data, expected_data)

    def test_apply_formatting_with_categorical_data(self) -> None:
        data = pd.DataFrame(
            {
                "A": pd.Categorical(["a", "b", "a"]),
                "B": [1, 2, 3],
            }
        )
        manager = self.factory.create()(data)

        format_mapping: FormatMapping = {
            "A": lambda x: x.upper(),
            "B": lambda x: x * 2,
        }

        formatted_data = manager.apply_formatting(format_mapping).data
        expected_data = pd.DataFrame(
            {
                "A": pd.Categorical(["A", "B", "A"]),
                "B": [2, 4, 6],
            }
        )
        assert_frame_equal(formatted_data, expected_data)

    def test_apply_formatting_with_datetime_index(self) -> None:
        data = pd.DataFrame(
            {
                "A": [1, 2, 3],
                "B": ["a", "b", "c"],
            },
            index=pd.to_datetime(["2021-01-01", "2021-01-02", "2021-01-03"]),
        )
        manager = self.factory.create()(data)

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
            "B": lambda x: x.upper(),
        }

        formatted_data = manager.apply_formatting(format_mapping).data
        expected_data = pd.DataFrame(
            {
                "A": [2, 4, 6],
                "B": ["A", "B", "C"],
            },
            index=pd.to_datetime(["2021-01-01", "2021-01-02", "2021-01-03"]),
        )
        assert_frame_equal(formatted_data, expected_data)

    def test_apply_formatting_with_complex_data(self) -> None:
        data = pd.DataFrame(
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
                "G": [None, "text", 3.14],
                "H": [1 + 2j, 3 + 4j, 5 + 6j],
            }
        )
        manager = self.factory.create()(data)

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
            "B": lambda x: x.upper(),
            "C": lambda x: f"{x:.2f}",
            "D": lambda x: not x,
            "E": lambda x: x.strftime("%Y-%m-%d"),
            "G": str,
            "H": abs,
        }

        formatted_data = manager.apply_formatting(format_mapping).data
        expected_data = pd.DataFrame(
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
                "G": [None, "text", "3.14"],
                "H": [2.23606797749979, 5.0, 7.810249675906654],
            }
        )
        assert_frame_equal(formatted_data, expected_data)

    def test_empty_dataframe(self) -> None:
        empty_df = pd.DataFrame()
        empty_manager = self.factory.create()(empty_df)
        assert empty_manager.get_num_rows() == 0
        assert empty_manager.get_num_columns() == 0
        assert empty_manager.get_column_names() == []
        assert empty_manager.get_field_types() == {}

    def test_dataframe_with_all_null_column(self) -> None:
        df = pd.DataFrame({"A": [1, 2, 3], "B": [None, None, None]})
        manager = self.factory.create()(df)
        summary = manager.get_summary("B")
        assert summary.nulls == 3
        assert summary.total == 3
        assert summary.unique is None

    def test_dataframe_with_mixed_types(self) -> None:
        df = pd.DataFrame({"A": [1, "two", 3.0, True]})
        manager = self.factory.create()(df)
        field_types = manager.get_field_types()
        assert field_types["A"] == ("string", "object")

    def test_search_with_regex(self) -> None:
        df = pd.DataFrame({"A": ["apple", "banana", "cherry"]})
        manager = self.factory.create()(df)
        result = manager.search("^[ab]")
        assert result.get_num_rows() == 2

    def test_sort_values_with_nulls(self) -> None:
        df = pd.DataFrame({"A": [3, 1, None, 2]})
        manager = self.factory.create()(df)
        sorted_manager = manager.sort_values("A", descending=True)
        assert sorted_manager.data["A"].to_list()[1:] == [
            3.0,
            2.0,
            1.0,
        ]

    def test_dataframe_with_multiindex(self) -> None:
        df = pd.DataFrame(
            {"A": [1, 2, 3, 4], "B": [5, 6, 7, 8]},
            index=[["a", "a", "b", "b"], [1, 2, 1, 2]],
        )
        manager = self.factory.create()(df)
        assert manager.get_row_headers() == ["", ""]
        assert manager.get_num_rows() == 4

    def test_get_field_types_with_datetime(self):
        import pandas as pd

        data = pd.DataFrame(
            {
                "date_col": [
                    datetime.date(2021, 1, 1),
                    datetime.date(2021, 1, 2),
                    datetime.date(2021, 1, 3),
                ],
                "datetime_col": [
                    datetime.datetime(2021, 1, 1),
                    datetime.datetime(2021, 1, 2),
                    datetime.datetime(2021, 1, 3),
                ],
                "time_col": [
                    datetime.time(1, 2, 3),
                    datetime.time(4, 5, 6),
                    datetime.time(7, 8, 9),
                ],
            }
        )
        manager = self.factory.create()(data)
        field_types = manager.get_field_types()

        assert field_types["date_col"] == ("string", "object")
        assert field_types["datetime_col"] == ("datetime", "datetime64[ns]")
        assert field_types["time_col"] == ("string", "object")
