"""合成 USDA ZIP 测试夹具。

真实数据集不适合放进单元测试，这里构造字段结构与真实 CSV 一致的小样本，
用于验证适配器语义、抽样规则与构建管线。
"""
from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

import pytest

FOUNDATION_ZIP = "FoodData_Central_foundation_food_csv_2026-04-30.zip"
SR_ZIP = "FoodData_Central_sr_legacy_food_csv_2018-04.zip"
SURVEY_ZIP = "FoodData_Central_survey_food_csv_2024-10-31.zip"
BRANDED_ZIP = "FoodData_Central_branded_food_csv_2026-04-30.zip"

NUTRIENT_HEADER = ["id", "name", "unit_name", "nutrient_nbr", "rank"]
NUTRIENTS = [
    ["1008", "Energy", "KCAL", "208", ""],
    ["1003", "Protein", "G", "203", ""],
    ["1004", "Total lipid (fat)", "G", "204", ""],
    ["1005", "Carbohydrate, by difference", "G", "205", ""],
    ["1079", "Fiber, total dietary", "G", "291", ""],
    ["2000", "Total Sugars", "G", "269", ""],
    ["1093", "Sodium, Na", "MG", "307", ""],
    ["1087", "Calcium, Ca", "MG", "301", ""],
    ["2047", "Energy (Atwater General Factors)", "KCAL", "957", ""],
    ["2048", "Energy (Atwater Specific Factors)", "KCAL", "958", ""],
    ["1062", "Energy", "kJ", "268", ""],
]
FOOD_HEADER = ["fdc_id", "data_type", "description", "food_category_id", "publication_date"]
NUTRIENT_ROW_HEADER = ["id", "fdc_id", "nutrient_id", "amount", "data_points"]
PORTION_HEADER = [
    "id", "fdc_id", "seq_num", "amount", "modifier", "portion_description",
    "gram_weight", "measure_unit_id",
]
CATEGORY_HEADER = ["id", "code", "description"]
MEASURE_HEADER = ["id", "name", "abbreviation"]
WWEIA_HEADER = ["wweia_food_category", "wweia_food_category_description"]
BRANDED_HEADER = [
    "fdc_id", "brand_owner", "brand_name", "gtin_upc", "serving_size", "serving_size_unit",
    "household_serving_fulltext", "branded_food_category", "discontinued_date", "ingredients",
]


def _write_zip(path: Path, files: dict[str, tuple[list[str], list[list[str]]]]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, (header, rows) in files.items():
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(header)
            writer.writerows(rows)
            zf.writestr(name, buffer.getvalue())


def _common_files() -> dict[str, tuple[list[str], list[list[str]]]]:
    return {
        "nutrient.csv": (NUTRIENT_HEADER, NUTRIENTS),
        "measure_unit.csv": (MEASURE_HEADER, [["1", "g", "g"], ["2", "ml", "ml"]]),
    }


def _foundation_files() -> dict[str, tuple[list[str], list[list[str]]]]:
    files = _common_files()
    files["food.csv"] = (FOOD_HEADER, [
        ["1001", "foundation_food", "Broccoli, raw", "11", "2020-01-01"],
        ["1002", "foundation_food", "Milk, whole", "1", "2020-01-01"],
        ["9001", "sub_sample_food", "Broccoli sample", "", "1/1/2020"],
    ])
    files["food_nutrient.csv"] = (NUTRIENT_ROW_HEADER, [
        ["1", "1001", "1008", "34", ""],
        ["2", "1001", "2048", "33", ""],
        ["3", "1001", "2047", "32", ""],
        ["4", "1001", "1003", "2.8", ""],
        ["5", "1001", "1005", "6.6", ""],
        ["6", "1001", "2066", "", ""],
        ["7", "1002", "2047", "61", ""],
        ["8", "1002", "2048", "", ""],
        ["9", "1002", "1003", "3.2", ""],
        ["10", "1002", "1005", "-1.0", ""],
        ["11", "1002", "1062", "255", ""],
        ["12", "1002", "1003", "3.3", ""],
        ["13", "9001", "1008", "99", ""],
    ])
    files["food_portion.csv"] = (PORTION_HEADER, [
        ["1", "1001", "1", "1", "", "cup", "100", "1"],
        ["2", "1002", "1", "1", "", "", "", "1"],
        ["3", "1002", "2", "1", "", "tbsp", "0", "1"],
    ])
    files["food_category.csv"] = (CATEGORY_HEADER, [
        ["11", "11", "Vegetables and Vegetable Products"],
        ["1", "1", "Dairy and Egg Products"],
    ])
    files["foundation_food.csv"] = (
        ["fdc_id", "NDB_number"], [["1001", "11090"], ["1002", "11090"]]
    )
    return files


def _sr_files() -> dict[str, tuple[list[str], list[list[str]]]]:
    files = _common_files()
    rows = []
    for index in range(30):
        rows.append([str(2000 + index), "sr_legacy_food", f"Food {index}", "11", "2018-04-01"])
    rows.append(["2999", "sr_legacy_food", "Dairy item", "1", "2018-04-01"])
    files["food.csv"] = (FOOD_HEADER, rows)
    nutrient_rows = []
    for index in range(31):
        food_id = 2000 + index if index < 30 else 2999
        nutrient_rows.append([str(index), str(food_id), "1008", "100", ""])
        nutrient_rows.append([f"p{index}", str(food_id), "1003", "5", ""])
    files["food_nutrient.csv"] = (NUTRIENT_ROW_HEADER, nutrient_rows)
    files["food_portion.csv"] = (PORTION_HEADER, [["1", "2000", "1", "1", "", "cup", "80", "1"]])
    files["food_category.csv"] = (CATEGORY_HEADER, [
        ["11", "11", "Vegetables and Vegetable Products"],
        ["1", "1", "Dairy and Egg Products"],
    ])
    return files


def _survey_files() -> dict[str, tuple[list[str], list[list[str]]]]:
    files = _common_files()
    categories = ["6407", "6402", "6404", "6409", "6413"]
    rows = []
    food_id = 6000
    for code in categories:
        for _ in range(5):
            food_id += 1
            rows.append([str(food_id), "survey_fndds_food", f"Survey food {food_id}", code, "2023-01-01"])
    rows.append(["2705383", "survey_fndds_food", "Milk, human", "9602", "2023-01-01"])
    files["food.csv"] = (FOOD_HEADER, rows)
    nutrient_rows = []
    counter = 0
    for row in rows:
        if row[0] == "2705383":
            continue
        counter += 1
        nutrient_rows.append([str(counter), row[0], "208", "120", ""])
        counter += 1
        nutrient_rows.append([str(counter), row[0], "203", "4.5", ""])
    files["food_nutrient.csv"] = (NUTRIENT_ROW_HEADER, nutrient_rows)
    files["food_portion.csv"] = (PORTION_HEADER, [["1", "6001", "1", "1", "", "cup", "150", "1"]])
    files["wweia_food_category.csv"] = (WWEIA_HEADER, [
        [code, f"Category {code}"] for code in categories
    ] + [["9602", "Human milk"]])
    return files


def _branded_files() -> dict[str, tuple[list[str], list[list[str]]]]:
    files = _common_files()
    files["food.csv"] = (FOOD_HEADER, [
        ["5001", "branded_food", "Brand cheese A", "", "2022-01-01"],
        ["5002", "branded_food", "Brand cheese A newer", "", "2024-01-01"],
        ["5003", "branded_food", "Brand yogurt no data", "", "2023-01-01"],
        ["5004", "branded_food", "Brand discontinued juice", "", "2021-01-01"],
        ["5005", "branded_food", "Brand cereal", "", "2023-06-01"],
        ["5006", "branded_food", "Brand unknown", "", "2023-07-01"],
    ])
    files["branded_food.csv"] = (BRANDED_HEADER, [
        ["5001", "Owner", "Cheese Co", "GTIN-A", "30", "g", "1 slice", "Cheese", "", "Milk, salt"],
        ["5002", "Owner", "Cheese Co", "GTIN-A", "30", "g", "1 slice", "Cheese", "", "Milk, salt"],
        ["5003", "Owner", "Yogurt Co", "GTIN-B", "170", "ml", "1 cup", "", "", "Milk, cultures"],
        ["5004", "Owner", "Juice Co", "GTIN-C", "240", "MLT", "1 cup", "Yogurt", "2023-01-01", "Water"],
        ["5005", "Owner", "Cereal Co", "GTIN-D", "1", "MG", "1 serving", "Cereal", "", "Oats"],
        ["5006", "Owner", "Unknown Co", "GTIN-E", "", "", "", "", "", ""],
    ])
    files["food_nutrient.csv"] = (NUTRIENT_ROW_HEADER, [
        ["1", "5001", "1008", "400", ""],
        ["2", "5001", "1003", "25", ""],
        ["3", "5002", "1008", "410", ""],
        ["4", "5004", "1008", "50", ""],
        ["5", "5005", "1008", "380", ""],
    ])
    return files


@pytest.fixture()
def synthetic_env(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_zip(data_dir / FOUNDATION_ZIP, _foundation_files())
    _write_zip(data_dir / SR_ZIP, _sr_files())
    _write_zip(data_dir / SURVEY_ZIP, _survey_files())
    _write_zip(data_dir / BRANDED_ZIP, _branded_files())

    sample_dir = tmp_path / "sample"
    formal_db = tmp_path / "formal" / "meal_canvas.sqlite"
    formal_branded = tmp_path / "formal" / "meal_canvas_branded.sqlite"
    monkeypatch.setenv("MEAL_CANVAS_DATA_DIR", str(data_dir))
    monkeypatch.setenv("MEAL_CANVAS_SAMPLE_DIR", str(sample_dir))
    monkeypatch.setenv("MEAL_CANVAS_DB_PATH", str(formal_db))
    monkeypatch.setenv("MEAL_CANVAS_BRANDED_DB_PATH", str(formal_branded))
    return {
        "data_dir": data_dir,
        "sample_dir": sample_dir,
        "formal_db": formal_db,
        "formal_branded": formal_branded,
    }
