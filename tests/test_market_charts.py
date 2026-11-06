import pandas as pd

from src.web_app.market_charts import index_history_chart


def test_index_chart_uses_data_extent_and_keeps_all_series():
    history = pd.DataFrame(
        {"S&P 500": [6000.0, 6200.0], "Dow Jones": [42000.0, 43000.0]},
        index=pd.to_datetime(["2025-01-02", "2025-01-03"]),
    )

    chart = index_history_chart(history, "Index level")
    spec = chart.to_dict()

    assert spec["encoding"]["y"]["scale"]["zero"] is False
    assert spec["encoding"]["y"]["title"] == "Index level"
    assert set(chart.data["Index"]) == {"S&P 500", "Dow Jones"}
    assert chart.data["Level"].min() == 6000.0
    assert chart.data["Level"].max() == 43000.0


def test_index_chart_excludes_missing_values():
    history = pd.DataFrame(
        {"S&P 500": [6000.0, None, 6200.0]},
        index=pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06"]),
    )

    chart = index_history_chart(history, "Index level")

    assert chart.data["Level"].tolist() == [6000.0, 6200.0]
