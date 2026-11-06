"""Charts for the market overview."""
import altair as alt
import pandas as pd


def index_history_chart(history: pd.DataFrame, y_label: str) -> alt.Chart:
    data = history.rename_axis("Date").reset_index().melt(
        id_vars="Date", var_name="Index", value_name="Level"
    ).dropna(subset=["Level"])
    return (
        alt.Chart(data)
        .mark_line()
        .encode(
            x=alt.X("Date:T", title="Date"),
            y=alt.Y("Level:Q", title=y_label, scale=alt.Scale(zero=False)),
            color=alt.Color("Index:N", title="Index"),
            tooltip=[
                alt.Tooltip("Date:T", title="Date"),
                alt.Tooltip("Index:N", title="Index"),
                alt.Tooltip("Level:Q", title=y_label, format=",.2f"),
            ],
        )
    )
