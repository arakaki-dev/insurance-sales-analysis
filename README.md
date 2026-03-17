# 📊 生命保険 アウトバウンドコール 営業成績分析ポートフォリオ

> **Life Insurance Outbound Call — Sales Performance Analysis**  
> BIエンジニアとしての分析・可視化スキルをデモンストレーションするポートフォリオ作品です。

---

## 🎯 プロジェクト概要

生命保険会社のアウトバウンドコール営業データを分析し、**成約率向上に向けたインサイトを導出する**分析パイプラインです。

- **分析期間**: 2024年1月〜12月（ダミーデータ）
- **データ規模**: 5,000コール / 15名の担当者 / 6商品
- **技術スタック**: Python / pandas / matplotlib / Streamlit

---

## 📁 ディレクトリ構成

```
insurance_portfolio/
├── generate_data.py        # ダミーデータ自動生成スクリプト
├── app.py                  # Streamlit インタラクティブダッシュボード
├── requirements.txt        # 依存ライブラリ
├── data/
│   ├── calls.csv           # コール履歴データ（自動生成）
│   ├── agents.csv          # 担当者マスタ
│   └── products.csv        # 商品マスタ
└── notebooks/
    └── analysis.ipynb      # 分析ノートブック（手順・思考プロセス付き）
```

---

## 🚀 セットアップ & 実行方法

### 1. リポジトリをクローン

```bash
git clone https://github.com/YOUR_USERNAME/insurance-sales-analysis.git
cd insurance-sales-analysis
```

### 2. ライブラリインストール

```bash
pip install -r requirements.txt
```

### 3. ダミーデータ生成

```bash
python generate_data.py
```

### 4. Jupyter Notebookで分析を確認

```bash
jupyter notebook notebooks/analysis.ipynb
```

### 5. Streamlit ダッシュボードを起動

```bash
streamlit run app.py
```

ブラウザで `http://localhost:8501` が自動で開きます。

---

## 📊 分析内容

| # | 分析項目 | 目的 |
|---|---------|------|
| 1 | **全体KPIサマリー** | 総コール数・成約数・成約率・接触率を一覧把握 |
| 2 | **担当者別パフォーマンス** | ハイパフォーマーの特定と経験年数との相関分析 |
| 3 | **時間帯別 成約率・接触率** | 最適なコールタイミングの特定 |
| 4 | **顧客属性クロス分析** | 年齢・性別 × 成約率でターゲット顧客を特定 |
| 5 | **商品別 成約実績** | 重点商品と推定年間収益の可視化 |
| 6 | **月次トレンド分析** | 季節変動・成約率の推移把握 |

---

## 🖼️ スクリーンショット

### KPI サマリー
![KPI Summary](notebooks/kpi_summary.png)

### 担当者別パフォーマンス
![Agent Performance](notebooks/agent_performance.png)

### 時間帯別分析
![Hourly Analysis](notebooks/hourly_analysis.png)

### 顧客属性クロス分析（年齢・性別）
![Customer Analysis](notebooks/customer_analysis.png)

### 月次トレンド
![Monthly Trend](notebooks/monthly_trend.png)

---

## 💡 主要インサイト（分析結果サマリー）

1. **経験年数と成約率に正の相関** — 経験5年以上の担当者は平均より約3〜5%高い成約率
2. **時間帯による成約率の差** — 特定の時間帯に成約が集中（最適コール時間あり）
3. **40〜50代が高成約率** — ターゲットリストの優先順位付けに活用可能
4. **個人年金・終身保険は推定収益が高い** — 重点商品として研修強化の余地あり

---

## 🔧 技術ポイント

- **データ生成の現実性**: 経験年数・時間帯・商品カテゴリに現実的な重み付けを実装
- **再現性**: `random.seed()` でデータ生成を完全再現可能
- **モジュール設計**: データ生成 / 分析 / 可視化を分離した保守性の高い構成
- **インタラクティブUI**: Streamlitでチーム・期間フィルター、CSVアップロード機能を実装

---

## 📬 お問い合わせ

ご質問・ご相談はお気軽にどうぞ。

---

*このポートフォリオはダミーデータを使用しています。実際の業務データは含みません。*
