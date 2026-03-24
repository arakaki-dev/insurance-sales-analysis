"""
tests/test_data.py
==================
データ品質検証テスト

- test_raw_*  : calls_raw.csv（ノイズあり生データ）に対するテスト
                → ノイズが意図通り注入されているかを確認
- test_clean_*: calls.csv（クレンジング済みデータ）に対するテスト
                → クレンジング後に期待するビジネスルールを満たすかを確認
"""

import os
import pandas as pd
import numpy as np
import pytest

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


# ──────────────────────────────────────────────────────────────────────────────
# フィクスチャ
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def calls_raw():
    path = os.path.join(DATA_DIR, "calls_raw.csv")
    return pd.read_csv(path, dtype=str)


@pytest.fixture(scope="module")
def calls():
    path = os.path.join(DATA_DIR, "calls.csv")
    return pd.read_csv(path)


@pytest.fixture(scope="module")
def agents():
    return pd.read_csv(os.path.join(DATA_DIR, "agents.csv"))


@pytest.fixture(scope="module")
def products():
    return pd.read_csv(os.path.join(DATA_DIR, "products.csv"))


# ──────────────────────────────────────────────────────────────────────────────
# マスタデータ（共通）
# ──────────────────────────────────────────────────────────────────────────────

def test_agents_columns(agents):
    expected = {"agent_id", "name", "team", "experience_years"}
    assert expected.issubset(set(agents.columns))


def test_agents_row_count(agents):
    assert len(agents) == 15


def test_products_columns(products):
    expected = {"product_id", "product_name", "monthly_premium", "category"}
    assert expected.issubset(set(products.columns))


def test_products_row_count(products):
    assert len(products) == 6


# ──────────────────────────────────────────────────────────────────────────────
# 生データ: ノイズが意図通り注入されているか
# ──────────────────────────────────────────────────────────────────────────────

def test_raw_row_count(calls_raw):
    assert len(calls_raw) == 5000


def test_raw_has_null_call_duration(calls_raw):
    """CTI連携失敗による call_duration_min の欠損が存在すること"""
    null_count = calls_raw["call_duration_min"].isna().sum()
    assert null_count > 0, "call_duration_min に欠損がありません（ノイズ注入を確認してください）"


def test_raw_has_null_age_group(calls_raw):
    """顧客情報未登録による customer_age_group の欠損が存在すること"""
    null_count = calls_raw["customer_age_group"].isna().sum()
    assert null_count > 0


def test_raw_has_null_gender(calls_raw):
    """顧客情報未登録による customer_gender の欠損が存在すること"""
    null_count = calls_raw["customer_gender"].isna().sum()
    assert null_count > 0


def test_raw_has_out_of_range_call_hour(calls_raw):
    """残業・テストデータ混入による call_hour 範囲外値が存在すること"""
    hours = pd.to_numeric(calls_raw["call_hour"], errors="coerce")
    out_of_range = hours[hours.notna() & ~hours.between(10, 19)]
    assert len(out_of_range) > 0


def test_raw_has_empty_call_result(calls_raw):
    """旧システム移行ゴミデータによる call_result 空文字/欠損が存在すること
    ※ pandas が CSV の空セルを NaN として読み込むため isna() も含めて確認する"""
    empty = calls_raw["call_result"].isna().sum() + (calls_raw["call_result"] == "").sum()
    assert empty > 0


def test_raw_has_mixed_datetime_format(calls_raw):
    """旧CTIシステムの日時フォーマット混在が存在すること"""
    old_format = calls_raw["call_datetime"].str.contains(r"^\d{4}/", regex=True, na=False).sum()
    assert old_format > 0, "旧フォーマット（YYYY/MM/DD）が見つかりません"


def test_raw_has_duplicate_phone_numbers(calls_raw):
    """コールリスト管理ミスによる重複電話番号が存在すること"""
    dup_count = calls_raw.duplicated(subset=["phone_number"], keep=False).sum()
    assert dup_count > 0


def test_raw_has_abnormal_duration(calls_raw):
    """システムバグによる call_duration_min の異常値（>60分）が存在すること"""
    dur = pd.to_numeric(calls_raw["call_duration_min"], errors="coerce")
    over_60 = (dur > 60).sum()
    assert over_60 > 0


# ──────────────────────────────────────────────────────────────────────────────
# クレンジング済みデータ: ビジネスルールを満たすか
# ──────────────────────────────────────────────────────────────────────────────

def test_clean_columns(calls):
    expected = {
        "call_id", "call_datetime", "call_date", "call_month",
        "call_hour", "agent_id", "phone_number", "customer_age_group",
        "customer_gender", "call_result", "product_id",
        "call_duration_min", "is_duplicate_call",
    }
    assert expected.issubset(set(calls.columns)), f"Missing: {expected - set(calls.columns)}"


def test_clean_row_count_less_than_raw(calls, calls_raw):
    """call_hour 範囲外レコード除外により、クリーンデータは生データより少ない"""
    assert len(calls) < len(calls_raw)


def test_clean_call_hour_range(calls):
    assert calls["call_hour"].between(10, 19).all(), "call_hour に範囲外の値があります"


def test_clean_no_null_call_duration(calls):
    assert calls["call_duration_min"].isna().sum() == 0, "call_duration_min に欠損があります"


def test_clean_duration_within_limit(calls):
    assert (calls["call_duration_min"] <= 60).all(), "call_duration_min に60分超の値があります"


def test_clean_no_empty_call_result(calls):
    empty = (calls["call_result"].astype(str).str.strip() == "").sum()
    assert empty == 0, "call_result に空文字があります"


def test_clean_call_result_values(calls):
    valid = {"成約", "検討中", "断り", "不在", "コールバック希望", "不明"}
    assert set(calls["call_result"].unique()).issubset(valid)


def test_clean_age_group_values(calls):
    valid = {"20代", "30代", "40代", "50代", "60代以上", "不明"}
    assert set(calls["customer_age_group"].unique()).issubset(valid)


def test_clean_gender_values(calls):
    valid = {"男性", "女性", "不明"}
    assert set(calls["customer_gender"].unique()).issubset(valid)


def test_clean_no_agent_id_whitespace(calls):
    """agent_id に余分なスペース（全角含む）がないこと"""
    has_space = calls["agent_id"].str.contains(r"\s", regex=True, na=False).sum()
    assert has_space == 0, f"agent_id に空白が {has_space}件残っています"


def test_clean_datetime_format_unified(calls):
    """call_datetime がすべて YYYY-MM-DD HH:MM 形式であること"""
    from datetime import datetime
    def is_valid_fmt(s):
        try:
            datetime.strptime(str(s), "%Y-%m-%d %H:%M")
            return True
        except ValueError:
            return False
    invalid = ~calls["call_datetime"].apply(is_valid_fmt)
    assert invalid.sum() == 0, f"フォーマット不正な call_datetime が {invalid.sum()}件あります"


def test_clean_all_agents_have_calls(calls, agents):
    """全担当者に最低1件のコールが紐付いていること"""
    agents_with_calls = set(calls["agent_id"].unique())
    all_agents = set(agents["agent_id"].unique())
    missing = all_agents - agents_with_calls
    assert not missing, f"コールのない担当者: {missing}"


def test_clean_no_duplicate_call_ids(calls):
    assert calls["call_id"].is_unique, "call_id に重複があります"


def test_clean_contract_rate_reasonable(calls):
    """成約率が現実的な範囲（5%〜30%）にあること"""
    rate = (calls["call_result"] == "成約").mean()
    assert 0.05 <= rate <= 0.30, f"成約率 {rate:.1%} が期待範囲外"


def test_clean_contact_rate_reasonable(calls):
    """接触率が現実的な範囲（50%〜90%）にあること"""
    rate = (calls["call_result"] != "不在").mean()
    assert 0.50 <= rate <= 0.90, f"接触率 {rate:.1%} が期待範囲外"


def test_clean_contracted_calls_have_product(calls):
    """成約コールには必ずproduct_idが設定されていること"""
    no_product = calls[(calls["call_result"] == "成約") & calls["product_id"].isna()]
    assert len(no_product) == 0


def test_clean_weekday_only_calls(calls):
    """コールが平日のみであること"""
    dates = pd.to_datetime(calls["call_date"])
    weekends = dates[dates.dt.dayofweek >= 5]
    assert len(weekends) == 0, f"土日のコールが {len(weekends)}件あります"


def test_clean_duplicate_call_flag_binary(calls):
    """is_duplicate_call が 0 or 1 のみであること"""
    assert set(calls["is_duplicate_call"].unique()).issubset({0, 1})


# ──────────────────────────────────────────────────────────────────────────────
# app.py との整合性チェック
# クレンジング後に生まれた値（'不明'等）がUIフィルターから漏れていないか検証する
# ──────────────────────────────────────────────────────────────────────────────

def test_app_age_order_covers_all_values(calls):
    """app.pyのage_orderがcalls.csvの全年齢層値をカバーしていること

    clean_data.pyが'不明'を補完した場合、app.pyのage_orderにも含まれていないと
    Streamlitのデフォルトフィルターからそのレコードが除外される。
    """
    import re
    import ast
    app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
    with open(app_path) as f:
        content = f.read()
    match = re.search(r"age_order\s*=\s*(\[.*?\])", content)
    assert match, "app.pyにage_orderが見つかりません"
    age_order = ast.literal_eval(match.group(1))
    actual_values = set(calls["customer_age_group"].dropna().unique())
    missing = actual_values - set(age_order)
    assert not missing, (
        f"app.pyのage_orderに含まれていない値: {missing}\n"
        "→ clean_data.pyのクレンジング後に追加された値と思われます。"
        "app.pyのage_orderに追加してください。"
    )
