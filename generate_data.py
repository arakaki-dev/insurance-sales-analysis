"""
generate_data.py
================
生命保険アウトバウンドコール 営業成績ダミーデータ生成スクリプト

実行方法:
    python generate_data.py

出力:
    data/calls.csv      - コール履歴データ
    data/agents.csv     - 担当者マスタ
    data/products.csv   - 商品マスタ
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
N_CALLS = 5000          # コール件数
N_AGENTS = 15           # 担当者数
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

# 時間帯（コール可能時間帯）
CALL_HOURS = list(range(10, 20))
HOUR_WEIGHTS = [0.05, 0.08, 0.12, 0.14, 0.12, 0.10, 0.10, 0.12, 0.12, 0.05]


def generate_calls(n_calls, agents, products):
    """コール履歴データを生成"""
    agent_ids = [a["agent_id"] for a in agents]
    product_ids = [p["product_id"] for p in products]

    # 経験年数が多いほど成約率が上がるように重み付け
    exp_map = {a["agent_id"]: a["experience_years"] for a in agents}

    records = []
    date_range = (END_DATE - START_DATE).days

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
        # 土日除く（簡易）
        while call_date.weekday() >= 5:
            call_date += timedelta(days=1)

        call_hour = random.choices(CALL_HOURS, weights=HOUR_WEIGHTS)[0]
        call_minute = random.randint(0, 59)
        call_datetime = call_date.replace(hour=call_hour, minute=call_minute)

        result = random.choices(CALL_RESULTS, weights=weights)[0]
        product_id = random.choice(product_ids) if result in ["成約", "検討中", "コールバック希望"] else None

        # 通話時間（成約は長め）
        if result == "成約":
            duration = random.randint(10, 35)
        elif result == "不在":
            duration = random.randint(0, 1)
        else:
            duration = random.randint(3, 15)

        age_group = random.choices(AGE_GROUPS, weights=AGE_WEIGHTS)[0]
        gender = random.choice(["男性", "女性"])

        records.append({
            "call_id": f"C{i+1:05d}",
            "call_datetime": call_datetime.strftime("%Y-%m-%d %H:%M"),
            "call_date": call_date.strftime("%Y-%m-%d"),
            "call_month": call_date.strftime("%Y-%m"),
            "call_hour": call_hour,
            "agent_id": agent_id,
            "customer_age_group": age_group,
            "customer_gender": gender,
            "call_result": result,
            "product_id": product_id,
            "call_duration_min": duration,
        })

    return pd.DataFrame(records)


def main():
    os.makedirs("data", exist_ok=True)

    # マスタ保存
    agents_df = pd.DataFrame(AGENTS)
    agents_df.to_csv("data/agents.csv", index=False, encoding="utf-8-sig")
    print(f"✅ agents.csv: {len(agents_df)} 件")

    products_df = pd.DataFrame(PRODUCTS)
    products_df.to_csv("data/products.csv", index=False, encoding="utf-8-sig")
    print(f"✅ products.csv: {len(products_df)} 件")

    # コール履歴生成
    calls_df = generate_calls(N_CALLS, AGENTS, PRODUCTS)
    calls_df.to_csv("data/calls.csv", index=False, encoding="utf-8-sig")
    print(f"✅ calls.csv: {len(calls_df)} 件")

    # サマリー表示
    print("\n📊 データサマリー")
    print(f"  期間: {calls_df['call_date'].min()} 〜 {calls_df['call_date'].max()}")
    print(f"  成約率: {(calls_df['call_result'] == '成約').mean():.1%}")
    print(f"  結果内訳:\n{calls_df['call_result'].value_counts().to_string()}")


if __name__ == "__main__":
    main()
