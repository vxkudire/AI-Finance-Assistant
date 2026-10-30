"""Compatibility helpers for warnings emitted by yfinance dependencies."""
import warnings
from contextlib import contextmanager

from pandas.errors import Pandas4Warning


@contextmanager
def ignore_yfinance_dataframe_inplace_warning():
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"The inplace keyword in DataFrame\.(?:sort_index|set_index) is deprecated.*",
            category=Pandas4Warning,
            module=r"yfinance\.utils",
        )
        yield
