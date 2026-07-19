import sqlite3
import pandas as pd


def load_dataframe_to_sql(df):

    conn = sqlite3.connect(":memory:")

    df.to_sql(
        "dataset",
        conn,
        index=False,
        if_exists="replace"
    )

    return conn