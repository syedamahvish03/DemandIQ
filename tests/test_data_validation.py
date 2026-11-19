import pandas as pd

from data_validation import validate_sales_data


def test_valid_data_is_cleaned_and_numeric():
    source = pd.DataFrame({
        " Date ": ["2025-01-01", "2025-01-02"],
        "STORE": [1, 1],
        "Item": [101, 102],
        "Sales": ["24", "13"],
    })
    cleaned, report = validate_sales_data(source)
    assert report["errors"] == []
    assert report["rows_received"] == 2
    assert report["rows_valid"] == 2
    assert pd.api.types.is_numeric_dtype(cleaned["sales"])
    assert pd.api.types.is_datetime64_any_dtype(cleaned["date"])


def test_invalid_rows_are_excluded_and_reported():
    source = pd.DataFrame({
        "date": ["2025-01-01", "not-a-date", "2025-01-03", "2025-01-04"],
        "store": [1, 1, 1, None],
        "item": [101, 101, 102, 103],
        "sales": ["10", "12", "-2", "8"],
    })
    cleaned, report = validate_sales_data(source)
    assert len(cleaned) == 1
    assert report["invalid_dates"] == 1
    assert report["negative_sales"] == 1
    assert report["missing_identifiers"] == 1
    assert report["rows_valid"] == 1


def test_missing_required_columns_is_an_error():
    cleaned, report = validate_sales_data(pd.DataFrame({"date": ["2025-01-01"]}))
    assert cleaned.empty
    assert any("Missing required columns" in error for error in report["errors"])


def test_duplicate_rows_are_flagged_but_retained():
    source = pd.DataFrame({
        "date": ["2025-01-01", "2025-01-01"],
        "store": [1, 1],
        "item": [101, 101],
        "sales": [10, 10],
    })
    cleaned, report = validate_sales_data(source)
    assert len(cleaned) == 2
    assert report["duplicate_rows"] == 1


def test_non_finite_sales_values_are_excluded_and_reported():
    source = pd.DataFrame({
        "date": ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"],
        "store": [1, 1, 1, 1],
        "item": [101, 101, 101, 101],
        "sales": [10, float("inf"), float("-inf"), 12],
    })

    cleaned, report = validate_sales_data(source)

    assert cleaned["sales"].tolist() == [10.0, 12.0]
    assert report["invalid_sales"] == 2
    assert report["negative_sales"] == 0
    assert report["rows_valid"] == 2
    assert any("non-finite sales" in warning for warning in report["warnings"])



def test_blank_identifiers_are_excluded_and_text_identifiers_are_trimmed():
    source = pd.DataFrame({
        "date": ["2025-01-01", "2025-01-02", "2025-01-03"],
        "store": [" STORE_A ", "   ", "STORE_B"],
        "item": [" ITEM_1 ", "ITEM_1", ""],
        "sales": [10, 12, 14],
    })

    cleaned, report = validate_sales_data(source)

    assert len(cleaned) == 1
    assert cleaned.loc[0, "store"] == "STORE_A"
    assert cleaned.loc[0, "item"] == "ITEM_1"
    assert report["missing_identifiers"] == 2
    assert report["rows_valid"] == 1
    assert any("missing store or item identifier" in warning for warning in report["warnings"])
