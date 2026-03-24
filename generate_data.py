"""
generate_data.py
================
生命保険アウトバウンドコール 営業成績ダミーデータ生成スクリプト

実行方法:
    python generate_data.py

出力:
    data/calls_raw.csv  - 生データ（現実的なノイズ・欠損を含む）
    data/agents.csv     - 担当者マスタ
    data/products.csv   - 商品マスタ

注意:
    クレンジング済みデータの生成は clean_data.py を実行してください。
    data/calls.csv が生成されます。
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import os

# 再現性のためシード固定
np.random.seed(42)
random.seed(42)

# ========== 設定 ==========
N_CALLS = 5000
N_AGENTS = 15
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2024, 12, 31)

# ========== マスタデータ ==========
AGENTS = [
    {"agent_id": f"A{i:03d}", "name": name, "team": team, "experience_years": exp}
    for i, (name, team, exp) in enumerate([
        ("田中 花子", "東京チーム", 5),
        ("佐藤 一郎", "東京チーム", 3),
        ("鈴木 美咲", "東京チーム", 7),
        ("高橋 健太", "東京チーム", 2),
        ("伊藤 さくら", "東京チーム", 4),
        ("渡辺 大輔", "大阪チーム", 6),
        ("山本 由美", "大阪チーム", 8),
        ("中村 翔太", "大阪チーム", 1),
        ("小林 奈々", "大阪チーム", 3),
        ("加藤 博之", "大阪チーム", 5),
        ("吉田 恵子", "名古屋チーム", 4),
        ("山田 拓也", "名古屋チーム", 2),
        ("佐々木 みゆ", "名古屋チーム", 6),
        ("松本 裕介", "名古屋チーム", 3),
        ("井上 千尋", "名古屋チーム", 9),
    ], start=1)
]

PRODUCTS = [
    {"product_id": "P001", "product_name": "終身保険プレミアム", "monthly_premium": 15000, "category": "終身保険"},
    {"product_id": "P002", "product_name": "定期保険スタンダード", "monthly_premium": 5000, "category": "定期保険"},
    {"product_id": "P003", "product_name": "医療保険ゴールド", "monthly_premium": 8000, "category": "医療保険"},
    {"product_id": "P004", "product_name": "がん保険エース", "monthly_premium": 6000, "category": "がん保険"},
    {"product_id": "P005", "product_name": "個人年金プラン", "monthly_premium": 20000, "category": "年金保険"},
    {"product_id": "P006", "product_name": "学資保険Kids", "monthly_premium": 12000, "category": "学資保険"},
]

CALL_RESULTS = ["成約", "検討中", "断り", "不在", "コールバック希望"]
RESULT_WEIGHTS = [0.12, 0.18, 0.30, 0.28, 0.12]

AGE_GROUPS = ["20代", "30代", "40代", "50代", "60代以上"]
AGE_WEIGHTS = [0.10, 0.25, 0.30, 0.25, 0.10]

CALL_HOURS = list(range(10, 20))
HOUR_WEIGHTS = [0.05, 0.08, 0.12, 0.14, 0.12, 0.10, 0.10, 0.12, 0.12, 0.05]


def _generate_phone_pool(n_unique: int) -> list:
    """電話番号プールを生成する（コールリスト管理ミスによる重複を含む）"""
    prefixes = ["090", "080", "070"]
    pool = set()
    while len(pool) < n_unique:
        prefix = random.choice(prefixes)
        mid = random.randint(1000, 9999)
        last = random.randint(1000, 9999)
        pool.add(f"{prefix}-{mid:04d}-{last:04d}")
    return list(pool)


def generate_calls(n_calls, agents, products):
    """コール履歴データを生成する"""
    agent_ids = [a["agent_id"] for a in agents]
    product_ids = [p["product_id"] for p in products]
    exp_map = {a["agent_id"]: a["experience_years"] for a in agents}
    date_range = (END_DATE - START_DATE).days

    # 電話番号プール: 約8%が重複（コールリスト管理ミスを模倣）
    n_unique_phones = int(n_calls * 0.92)
    phone_pool = _generate_phone_pool(n_unique_phones)

    records = []
    for i in range(n_calls):
        agent_id = random.choice(agent_ids)
        exp = exp_map[agent_id]

        # 経験年数補正（最大+8%）
        contract_boost = min(exp * 0.01, 0.08)
        weights = RESULT_WEIGHTS.copy()
        weights[0] += contract_boost
        weights[2] -= contract_boost
        weights = [max(w, 0.01) for w in weights]
        total = sum(weights)
        weights = [w / total for w in weights]

        call_date = START_DATE + timedelta(days=random.randint(0, date_range))
        while call_date.weekday() >= 5:
            call_date += timedelta(days=1)

        call_hour = random.choices(CALL_HOURS, weights=HOUR_WEIGHTS)[0]
        call_minute = random.randint(0, 59)
        call_datetime = call_date.replace(hour=call_hour, minute=call_minute)

        result = random.choices(CALL_RESULTS, weights=weights)[0]
        product_id = (
            random.choice(product_ids)
            if result in ["成約", "検討中", "コールバック希望"]
            else None
        )

        if result == "成約":
            duration = random.randint(10, 35)
        elif result == "不在":
            duration = random.randint(0, 1)
        else:
            duration = random.randint(3, 15)

        age_group = random.choices(AGE_GROUPS, weights=AGE_WEIGHTS)[0]
        gender = random.choice(["男性", "女性"])
        phone_number = random.choice(phone_pool)

        records.append({
            "call_id": f"C{i+1:05d}",
            "call_datetime": call_datetime.strftime("%Y-%m-%d %H:%M"),
            "call_date": call_date.strftime("%Y-%m-%d"),
            "call_month": call_date.strftime("%Y-%m"),
            "call_hour": call_hour,
            "agent_id": agent_id,
            "phone_number": phone_number,
            "customer_age_group": age_group,
            "customer_gender": gender,
            "call_result": result,
            "product_id": product_id,
            "call_duration_min": duration,
        })

    return pd.DataFrame(records)


def add_realistic_noise(df: pd.DataFrame) -> pd.DataFrame:
    """
    CTI/CRMシステムで現実に起こりうるデータ品質問題を意図的に注入する。

    注入する問題（8種類）:
    ┌──┬────────────────────────────────┬────────────────────────────────────────────┐
    │# │ 問題                           │ 現実の原因                                 │
    ├──┼────────────────────────────────┼────────────────────────────────────────────┤
    │1 │ call_duration_min 欠損 (~3%)   │ CTI連携失敗でログが記録されなかった         │
    │2 │ customer_age_group 欠損 (~7%)  │ 購入リスト顧客は属性情報が未登録           │
    │3 │ customer_gender 欠損 (~4%)     │ 同上                                       │
    │4 │ call_hour 範囲外 (~1%)        │ 残業・システムテストデータの混入            │
    │5 │ call_result 空文字 (~0.5%)     │ 旧システム移行時のデータ不整合             │
    │6 │ call_datetime フォーマット混在  │ 旧CTIシステム（YYYY/MM/DD HH:MM:SS形式）  │
    │  │ (~2%)                          │                                            │
    │7 │ call_duration_min 異常値 (~0.8%)│ システムバグで通話終了が記録されなかった   │
    │8 │ agent_id 全角スペース混入(~0.3%)│ 手動入力・コピペ時の表記揺れ              │
    └──┴────────────────────────────────┴────────────────────────────────────────────┘

    → clean_data.py でこれらを検出・修正・除外します。
    """
    rng = np.random.default_rng(seed=99)  # noiseは別シードで管理
    n = len(df)
    df = df.copy()

    # 1. call_duration_min の欠損（CTI連携失敗: ~3%）
    mask = rng.random(n) < 0.03
    df.loc[mask, "call_duration_min"] = np.nan

    # 2. customer_age_group の欠損（顧客情報未登録: ~7%）
    mask = rng.random(n) < 0.07
    df.loc[mask, "customer_age_group"] = np.nan

    # 3. customer_gender の欠損（顧客情報未登録: ~4%）
    mask = rng.random(n) < 0.04
    df.loc[mask, "customer_gender"] = np.nan

    # 4. call_hour の範囲外値（残業・テストデータ混入: ~1%）
    idx = rng.choice(n, size=int(n * 0.01), replace=False)
    df.loc[idx, "call_hour"] = rng.choice([8, 9, 20, 21], size=len(idx))

    # 5. call_result の空文字（旧システム移行ゴミデータ: ~0.5%）
    idx = rng.choice(n, size=int(n * 0.005), replace=False)
    df.loc[idx, "call_result"] = ""

    # 6. call_datetime フォーマット混在（旧CTI: 'YYYY/MM/DD HH:MM:SS': ~2%）
    idx = rng.choice(n, size=int(n * 0.02), replace=False)
    for i in idx:
        raw = str(df.loc[i, "call_datetime"])
        try:
            dt = datetime.strptime(raw, "%Y-%m-%d %H:%M")
            df.loc[i, "call_datetime"] = dt.strftime("%Y/%m/%d %H:%M:%S")
        except Exception:
            pass

    # 7. call_duration_min の異常値（システムバグ, 60分超: ~0.8%）
    valid_idx = df.index[df["call_duration_min"].notna()].tolist()
    n_outlier = int(n * 0.008)
    chosen = rng.choice(valid_idx, size=min(n_outlier, len(valid_idx)), replace=False)
    df.loc[chosen, "call_duration_min"] = rng.integers(61, 180, size=len(chosen)).astype(float)

    # 8. agent_id の全角スペース混入（手動入力ミス: ~0.3%）
    idx = rng.choice(n, size=int(n * 0.003), replace=False)
    df.loc[idx, "agent_id"] = df.loc[idx, "agent_id"] + "\u3000"  # 全角スペース

    return df


def main():
    os.makedirs("data", exist_ok=True)

    # マスタ保存
    agents_df = pd.DataFrame(AGENTS)
    agents_df.to_csv("data/agents.csv", index=False, encoding="utf-8-sig")
    print(f"✅ agents.csv: {len(agents_df)} 件")

    products_df = pd.DataFrame(PRODUCTS)
    products_df.to_csv("data/products.csv", index=False, encoding="utf-8-sig")
    print(f"✅ products.csv: {len(products_df)} 件")

    # コール履歴生成（クリーンデータ）
    calls_df = generate_calls(N_CALLS, AGENTS, PRODUCTS)

    # ノイズ注入 → 生データとして保存
    calls_raw_df = add_realistic_noise(calls_df)
    calls_raw_df.to_csv("data/calls_raw.csv", index=False, encoding="utf-8-sig")
    print(f"✅ calls_raw.csv: {len(calls_raw_df)} 件（ノイズ注入済み）")

    # サマリー表示
    print("\n📊 生データ品質サマリー（クレンジング前）")
    for col in ["call_duration_min", "customer_age_group", "customer_gender"]:
        null_count = calls_raw_df[col].isna().sum()
        print(f"  [{col}] 欠損: {null_count}件 ({null_count/len(calls_raw_df):.1%})")
    empty_result = (calls_raw_df["call_result"] == "").sum()
    print(f"  [call_result] 空文字: {empty_result}件")
    out_of_hour = (~calls_raw_df["call_hour"].between(10, 19)).sum()
    print(f"  [call_hour] 範囲外: {out_of_hour}件")
    dup_phones = calls_raw_df.duplicated(subset=["phone_number"], keep=False).sum()
    print(f"  [phone_number] 重複コール: {dup_phones}件")
    print(f"\n→ 次のステップ: python clean_data.py")


if __name__ == "__main__":
    main()
