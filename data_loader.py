"""CSV loading helpers for DemandIQ sales data."""
from pathlib import Path
from typing import Union

import pandas as pd

from data_validation import validate_sales_data


def load_sales_csv(source: Union[str, Path, object]):
    """Read a CSV source and return its validated dataframe and quality report."""
    raw = pd.read_csv(source)
    return validate_sales_data(raw)
