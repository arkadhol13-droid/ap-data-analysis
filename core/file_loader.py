import pandas as pd
import numpy as np

def load_file(uploaded_file):

    if uploaded_file.name.endswith(".csv"):

        df = pd.read_csv(uploaded_file)

    else:

        df = pd.read_excel(uploaded_file)

    df.replace(
        [
            "",
            " ",
            "NULL",
            "null",
            "None",
            "none",
            "N/A",
            "n/a"
        ],
        np.nan,
        inplace=True
    )

    return df