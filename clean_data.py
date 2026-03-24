"""
clean_data.py
=============
calls_raw.csv に含まれるデータ品質問題を検出・修正し、calls.csv を生成する。

対象の問題と処理方針:
┌──┬─────────────────────────────────┬──────────────────────────────────────────┐
│# │ 問題                            │ 処理方針                                 │
├──┼─────────────────────────────────┼──────────────────────────────────────────┤
│1 │ call_duration_min 欠損          │ 通話結果ごとの中央値で補完               │
│2 │ customer_age_group 欠損         │ '不明' で補完（分析時にセグメント除外）  │
│3 │ customer_gender 欠損            │ '不明' で補完                            │
│4 │ call_hour 範囲外（営業時間外）  │ レコード除外（記録不正とみなす）         │
│5 │ call_result 空文字              │ '不明' に置換                            │
│6 │ call_datetime フォーマット混在  │ 統一フォーマット（YYYY-MM-DD HH:MM）に変換│
│7 │ call_duration_min 異常値(>60分) │ 60分上限でクリッピング                   │
│8 │ agent_id 表記揺れ（全角スペース）│ strip() で正規化                        │
│9 │ phone_number 重複コール         │ フラグ列を追加（除外はせず可視化に活用） │
└──┴─────────────────────────────────┴──────────────────────────────────────────┘

実行方法:
    python clean_data.py
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime

RAW_PATH = "data/calls_raw.csv"
CLEAN_PATH = "data/calls.csv"
VALID_HOURS = range(10, 20)
MAX_DURATION_MIN = 60


# ──────────────────────────────────────────────────────────────────────────────
# 品質レポート
# ──────────────────────────────────────────────────────────────────────────────

def report_quality(df: pd.DataFrame, label: str = "") -> dict:
    """データ品質の問題件数をカウントしてレポートする"""
    issues = {}

    # 欠損
    for col in df.columns:
        null_count = df[col].isna().sum()
        empty_count = (df[col].astype(str) == "").sum() if df[col].dtype == object else 0
        total = null_count + empty_count
        if total > 0:
            issues[f"{col}_null_or_empty"] = int(total)

    # call_hour 範囲外
    if "call_hour" in df.columns:
        numeric_hour = pd.to_numeric(df["call_hour"], errors="coerce")
        out_of_range = numeric_hour.isna() | ~numeric_hour.between(10, 19)
        issues["call_hour_out_of_range"] = int(out_of_range.sum())

    # call_duration_min 異常値（>60分）
    if "call_duration_min" in df.columns:
        numeric_dur = pd.to_numeric(df["call_duration_min"], errors="coerce")
        over_max = (numeric_dur > MAX_DURATION_MIN).sum()
        if over_max > 0:
            issues["call_duration_over_60min"] = int(over_max)

    # call_datetime フォーマット混在
    if "call_datetime" in df.columns:
        bad_fmt = df["call_datetime"].apply(_parse_datetime).isna().sum()
        if bad_fmt > 0:
            issues["call_datetime_bad_format"] = int(bad_fmt)

    # phone_number 重複
    if "phone_number" in df.columns:
        dup_phones = df.duplicated(subset=["phone_number"], keep=False).sum()
        if dup_phones > 0:
            issues["phone_number_duplicate_calls"] = int(dup_phones)

    n = len(df)
    print(f"\n{'─'*55}")
    print(f"  データ品質レポート: {label}（{n:,}件）")
    print(f"{'─'*55}")
    if not issues:
        print("  ✅ 問題なし")
    for key, count in sorted(issues.items()):
        print(f"  ⚠️  {key}: {count}件 ({count/n:.1%})")
    print(f"{'─'*55}")

    return issues


# ──────────────────────────────────────────────────────────────────────────────
# クレンジング関数
# ──────────────────────────────────────────────────────────────────────────────

def _parse_datetime(s: str):
    """複数フォーマットの日時文字列を統一フォーマットへ変換する"""
    for fmt in ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(str(s), fmt).strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            continue
    return None


def fix_agent_id(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """agent_id の表記揺れ（全角スペース等）を正規化する"""
    before = df["agent_id"].copy()
    df["agent_id"] = df["agent_id"].str.strip()
    changed = (before != df["agent_id"]).sum()
    return df, int(changed)


def fix_datetime_format(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """call_datetime のフォーマットを統一する（YYYY-MM-DD HH:MM）"""
    parsed = df["call_datetime"].apply(_parse_datetime)
    bad_count = parsed.isna().sum()
    df["call_datetime"] = parsed
    return df, int(bad_count)


def remove_invalid_call_hour(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """営業時間外のコール（call_hour が 10〜19 以外）を除外する"""
    df["call_hour"] = pd.to_numeric(df["call_hour"], errors="coerce")
    invalid = df["call_hour"].isna() | ~df["call_hour"].between(10, 19)
    removed = int(invalid.sum())
    df = df[~invalid].copy()
    df["call_hour"] = df["call_hour"].astype(int)
    return df, removed


def fix_call_result(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """call_result の空文字を '不明' に置換する"""
    mask = df["call_result"].isna() | (df["call_result"].str.strip() == "")
    count = int(mask.sum())
    df.loc[mask, "call_result"] = "不明"
    return df, count


def impute_call_duration(df: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
    """
    call_duration_min の欠損値を通話結果ごとの中央値で補完し、
    60分超の異常値を上限クリッピングする。
    """
    df["call_duration_min"] = pd.to_numeric(df["call_duration_min"], errors="coerce")

    # 通話結果ごとの中央値（欠損を除いた値から計算）
    median_by_result = (
        df.groupby("call_result")["call_duration_min"]
        .median()
        .to_dict()
    )
    overall_median = df["call_duration_min"].median()

    null_count = int(df["call_duration_min"].isna().sum())
    df["call_duration_min"] = df.apply(
        lambda row: (
            median_by_result.get(row["call_result"], overall_median)
            if pd.isna(row["call_duration_min"])
            else row["call_duration_min"]
        ),
        axis=1,
    )

    over_max = int((df["call_duration_min"] > MAX_DURATION_MIN).sum())
    df["call_duration_min"] = df["call_duration_min"].clip(upper=MAX_DURATION_MIN)
    df["call_duration_min"] = df["call_duration_min"].round(1)

    return df, null_count, over_max


def impute_customer_attributes(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """customer_age_group / customer_gender の欠損を '不明' で補完する"""
    counts = {}
    for col in ["customer_age_group", "customer_gender"]:
        null_count = df[col].isna().sum() + (df[col].astype(str) == "").sum()
        df[col] = df[col].fillna("不明").replace("", "不明")
        counts[col] = int(null_count)
    return df, counts


def flag_duplicate_calls(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """同一電話番号への重複コールにフラグを付与する（除外はしない）"""
    df["is_duplicate_call"] = df.duplicated(subset=["phone_number"], keep=False).astype(int)
    dup_count = int(df["is_duplicate_call"].sum())
    return df, dup_count


# ──────────────────────────────────────────────────────────────────────────────
# メインパイプライン
# ──────────────────────────────────────────────────────────────────────────────

def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """クレンジングパイプラインを実行する"""
    log = {}

    df, n = fix_agent_id(df)
    log["agent_id_normalized"] = n

    df, n = fix_datetime_format(df)
    log["datetime_format_fixed"] = n

    df, n = remove_invalid_call_hour(df)
    log["call_hour_removed"] = n

    df, n = fix_call_result(df)
    log["call_result_set_unknown"] = n

    df, null_n, clip_n = impute_call_duration(df)
    log["duration_imputed"] = null_n
    log["duration_clipped"] = clip_n

    df, attr_counts = impute_customer_attributes(df)
    log.update({f"{k}_imputed": v for k, v in attr_counts.items()})

    df, n = flag_duplicate_calls(df)
    log["duplicate_calls_flagged"] = n

    return df.reset_index(drop=True), log


def main():
    print(f"[1/4] 生データ読み込み: {RAW_PATH}")
    if not os.path.exists(RAW_PATH):
        raise FileNotFoundError(
            f"{RAW_PATH} が見つかりません。先に python generate_data.py を実行してください。"
        )
    df_raw = pd.read_csv(RAW_PATH, dtype=str)
    report_quality(df_raw, "クレンジング前（生データ）")

    print(f"\n[2/4] クレンジング実行...")
    df_clean, log = clean(df_raw)

    print(f"\n[3/4] 処理サマリー:")
    for key, count in log.items():
        if count > 0:
            mark = "🗑️ " if "removed" in key else "✅"
            print(f"  {mark} {key}: {count}件")

    report_quality(df_clean, "クレンジング後")

    print(f"\n[4/4] 保存: {CLEAN_PATH}")
    os.makedirs("data", exist_ok=True)
    df_clean.to_csv(CLEAN_PATH, index=False, encoding="utf-8-sig")
    print(f"  → {len(df_clean):,} 件を保存しました（{len(df_raw) - len(df_clean)}件を除外）")


if __name__ == "__main__":
    main()
