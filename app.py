"""
app.py - 生命保険アウトバウンドコール 営業成績ダッシュボード
======================================================
実行方法: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker
import matplotlib.font_manager as fm
import io
import os
from scipy import stats
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold

# 日本語フォント設定（リポジトリ内のフォントファイルを使用）
_font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'IPAGothic.ttf')
if os.path.exists(_font_path):
    fm.fontManager.addfont(_font_path)
    _prop = fm.FontProperties(fname=_font_path)
    matplotlib.rcParams['font.family'] = _prop.get_name()
matplotlib.rcParams['axes.unicode_minus'] = False

# ページ設定
st.set_page_config(
    page_title="保険営業成績ダッシュボード",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ===== スタイル =====
st.markdown("""
<style>
.metric-card {
    background-color: white;
    border-radius: 10px;
    padding: 20px;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.metric-value { font-size: 2.2rem; font-weight: 700; }
.metric-label { font-size: 0.9rem; color: #6B7280; margin-top: 4px; }
.section-header {
    font-size: 1.2rem; font-weight: 600;
    border-left: 4px solid #2563EB;
    padding-left: 10px; margin: 24px 0 12px 0;
}
.insight-box {
    background-color: #EFF6FF;
    border-left: 4px solid #2563EB;
    border-radius: 6px;
    padding: 12px 16px;
    margin: 8px 0 16px 0;
    font-size: 0.92rem;
    color: #1E40AF;
}
</style>
""", unsafe_allow_html=True)

COLORS = {
    'primary': '#2563EB', 'success': '#16A34A',
    'warning': '#D97706', 'danger': '#DC2626', 'neutral': '#6B7280',
}
TEAM_COLORS = {'東京チーム': '#2563EB', '大阪チーム': '#16A34A', '名古屋チーム': '#D97706'}


# ===== データ読み込み =====
@st.cache_data
def load_data(calls_file=None, agents_file=None, products_file=None):
    """CSVを読み込んでマージ"""
    if calls_file:
        calls = pd.read_csv(calls_file)
        agents = pd.read_csv(agents_file) if agents_file else pd.read_csv("data/agents.csv")
        products = pd.read_csv(products_file) if products_file else pd.read_csv("data/products.csv")
    else:
        calls = pd.read_csv("data/calls.csv")
        agents = pd.read_csv("data/agents.csv")
        products = pd.read_csv("data/products.csv")

    df = calls.merge(agents, on='agent_id', how='left').merge(products, on='product_id', how='left')
    df['is_contracted'] = (df['call_result'] == '成約').astype(int)
    df['is_contacted']  = (df['call_result'] != '不在').astype(int)
    df['call_date'] = pd.to_datetime(df['call_date'])
    return df, agents, products


# ===== サイドバー =====
st.sidebar.title("📁 データ設定")
st.sidebar.markdown("---")

use_upload = st.sidebar.checkbox("CSVをアップロードして分析", value=False)
calls_upload = agents_upload = products_upload = None

if use_upload:
    calls_upload   = st.sidebar.file_uploader("calls.csv", type="csv")
    agents_upload  = st.sidebar.file_uploader("agents.csv", type="csv")
    products_upload = st.sidebar.file_uploader("products.csv", type="csv")
    if not calls_upload:
        st.sidebar.info("calls.csv をアップロードしてください")

df, agents_df, products_df = load_data(calls_upload, agents_upload, products_upload)

st.sidebar.markdown("---")
st.sidebar.markdown("**フィルター**")

# チームフィルター
all_teams = sorted(df['team'].dropna().unique().tolist())
selected_teams = st.sidebar.multiselect("チーム", all_teams, default=all_teams)

# 期間フィルター
min_date = df['call_date'].min().date()
max_date = df['call_date'].max().date()
date_range = st.sidebar.date_input("期間", value=(min_date, max_date), min_value=min_date, max_value=max_date)

# 商品カテゴリーフィルター
all_categories = sorted(df['category'].dropna().unique().tolist())
selected_categories = st.sidebar.multiselect("商品カテゴリー", all_categories, default=all_categories)

# コール結果フィルター
all_results = sorted(df['call_result'].dropna().unique().tolist())
selected_results = st.sidebar.multiselect("コール結果", all_results, default=all_results)

# 顧客属性フィルター
st.sidebar.markdown("**顧客属性**")
age_order = ['20代', '30代', '40代', '50代', '60代以上', '不明']
all_ages = [a for a in age_order if a in df['customer_age_group'].unique()]
selected_ages = st.sidebar.multiselect("年齢層", all_ages, default=all_ages)

all_genders = sorted(df['customer_gender'].dropna().unique().tolist())
selected_genders = st.sidebar.multiselect("性別", all_genders, default=all_genders)

# 担当者フィルター
all_agents = sorted(df['name'].dropna().unique().tolist())
selected_agents = st.sidebar.multiselect("担当者", all_agents, default=all_agents)

# ===== フィルター適用 =====
if len(date_range) == 2:
    df_filtered = df[
        (df['team'].isin(selected_teams)) &
        (df['call_date'].dt.date >= date_range[0]) &
        (df['call_date'].dt.date <= date_range[1]) &
        (df['call_result'].isin(selected_results)) &
        (df['customer_age_group'].isin(selected_ages)) &
        (df['customer_gender'].isin(selected_genders)) &
        (df['name'].isin(selected_agents))
    ]
    # 商品カテゴリーは成約データのみ対象（未成約はcategoryがNaN）
    df_filtered = df_filtered[
        (df_filtered['category'].isna()) | (df_filtered['category'].isin(selected_categories))
    ]
else:
    df_filtered = df[df['team'].isin(selected_teams)]


# ===== メインコンテンツ =====
st.title("📊 生命保険 アウトバウンドコール 営業成績ダッシュボード")
st.caption(f"分析期間: {df_filtered['call_date'].min().strftime('%Y/%m/%d')} 〜 {df_filtered['call_date'].max().strftime('%Y/%m/%d')}  |  チーム: {', '.join(selected_teams)}  |  担当者: {len(selected_agents)}名  |  {len(df_filtered):,}件")

# ===== KPIカード =====
st.markdown('<div class="section-header">📌 KPIサマリー</div>', unsafe_allow_html=True)
col1, col2, col3, col4 = st.columns(4)

total_calls     = len(df_filtered)
total_contracts = df_filtered['is_contracted'].sum()
contract_rate   = df_filtered['is_contracted'].mean()
contact_rate    = df_filtered['is_contacted'].mean()

for col, val, label, color in [
    (col1, f"{total_calls:,}", "総コール数", COLORS['primary']),
    (col2, f"{total_contracts:,}", "成約数", COLORS['success']),
    (col3, f"{contract_rate:.1%}", "成約率", COLORS['warning']),
    (col4, f"{contact_rate:.1%}", "接触率", COLORS['neutral']),
]:
    with col:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color:{color}">{val}</div>
            <div class="metric-label">{label}</div>
        </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# KPI インサイト（フィルター連動）
contacted_calls  = df_filtered['is_contacted'].sum()
not_contacted    = total_calls - contacted_calls
lost_opportunity = not_contacted * contract_rate
absence_rate     = not_contacted / total_calls if total_calls > 0 else 0

# 全体データと比較
overall_contract_rate = df['is_contracted'].mean()
rate_diff = contract_rate - overall_contract_rate
diff_label = f"+{rate_diff:.1%}ポイント（全体平均より高い）" if rate_diff > 0 else f"{rate_diff:.1%}ポイント（全体平均より低い）"
diff_color = COLORS['success'] if rate_diff >= 0 else COLORS['danger']

filter_label = "・".join(selected_teams) if len(selected_teams) < len(all_teams) else "全チーム"

st.markdown(f"""
<div class="insight-box">
💡 <b>現在の絞り込み条件：{filter_label} ／ {len(selected_agents)}名 ／ {len(df_filtered):,}件</b><br><br>
📞 不在率は <b>{absence_rate:.1%}</b>（{not_contacted:,}件が未接触）。
接触できていれば追加で約 <b>{lost_opportunity:.0f}件</b> の成約が見込めました。<br>
📈 現在の成約率 <b>{contract_rate:.1%}</b> は全体平均（{overall_contract_rate:.1%}）と比べ
<b style="color:{diff_color}">{diff_label}</b>。<br>
💰 現在の月間推定収益：成約1件あたりの平均保険料を仮定すると、
不在分の機会損失は年換算で約 <b>{lost_opportunity * 12:.0f}件分</b> に相当します。
</div>
""", unsafe_allow_html=True)

# ===== 担当者パフォーマンス =====
st.markdown('<div class="section-header">👤 担当者別パフォーマンス</div>', unsafe_allow_html=True)
col_left, col_right = st.columns(2)

agent_stats = df_filtered.groupby(['agent_id', 'name', 'team', 'experience_years']).agg(
    calls=('call_id', 'count'),
    contracts=('is_contracted', 'sum'),
).reset_index()
agent_stats['contract_rate'] = agent_stats['contracts'] / agent_stats['calls']
agent_stats = agent_stats.sort_values('contract_rate', ascending=False)

with col_left:
    fig, ax = plt.subplots(figsize=(7, 5.5))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    colors = [TEAM_COLORS.get(t, COLORS['neutral']) for t in agent_stats['team']]
    bars = ax.barh(agent_stats['name'], agent_stats['contract_rate'], color=colors, alpha=0.85)
    ax.axvline(agent_stats['contract_rate'].mean(), color='red', linestyle='--', linewidth=1.5, label='Average')
    for bar, val in zip(bars, agent_stats['contract_rate']):
        ax.text(val + 0.002, bar.get_y() + bar.get_height()/2, f'{val:.1%}', va='center', fontsize=9)
    patches = [mpatches.Patch(color=c, label=t) for t, c in TEAM_COLORS.items()]
    ax.legend(handles=patches, fontsize=8)
    ax.set_title('成約率ランキング', fontweight='bold')
    ax.set_xlabel('Contract Rate')
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

with col_right:
    fig, ax = plt.subplots(figsize=(7, 5.5))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    for team, grp in agent_stats.groupby('team'):
        ax.scatter(grp['experience_years'], grp['contract_rate'],
                   color=TEAM_COLORS.get(team, COLORS['neutral']),
                   s=grp['calls'] * 0.3, alpha=0.8, label=team)
        for _, row in grp.iterrows():
            ax.annotate(row['name'].split()[0],
                        (row['experience_years'], row['contract_rate']),
                        textcoords='offset points', xytext=(5, 3), fontsize=8)
    x = agent_stats['experience_years'].values
    y = agent_stats['contract_rate'].values
    if len(x) > 1:
        z = np.polyfit(x, y, 1)
        xl = np.linspace(x.min(), x.max(), 100)
        ax.plot(xl, np.poly1d(z)(xl), 'r--', linewidth=1.5, alpha=0.7, label='Trend')
    ax.set_xlabel('Experience (years)')
    ax.set_ylabel('成約率')
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_title('経験年数 vs 成約率\n(バブルサイズ = コール数)', fontweight='bold')
    ax.legend(fontsize=8)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

# 担当者 インサイト（フィルター連動）
top_agent    = agent_stats.iloc[0]
bottom_agent = agent_stats.iloc[-1]
avg_rate     = agent_stats['contract_rate'].mean()
gap          = top_agent['contract_rate'] - avg_rate
gap_bottom   = avg_rate - bottom_agent['contract_rate']
gap_contracts = int(gap * agent_stats['calls'].mean())
if_bottom_avg = int(gap_bottom * bottom_agent['calls'])

st.markdown(f"""
<div class="insight-box">
💡 <b>現在表示中 {len(agent_stats)}名の担当者</b><br><br>
🏆 トップ：<b>{top_agent['name']}</b>（{top_agent['contract_rate']:.1%}）は平均より
<b>{gap:.1%}ポイント</b> 高く、月間約 <b>{gap_contracts}件</b> の上乗せ効果あり。<br>
⚠️ 最下位：<b>{bottom_agent['name']}</b>（{bottom_agent['contract_rate']:.1%}）が平均水準に達するだけで
月間約 <b>{if_bottom_avg}件</b> の成約増が見込めます。<br>
→ トップのトーク手法を横展開し、下位担当者への個別フォローを優先することを推奨します。
</div>
""", unsafe_allow_html=True)

# 詳細テーブル
with st.expander("📋 担当者詳細データを表示"):
    disp = agent_stats[['name', 'team', 'experience_years', 'calls', 'contracts', 'contract_rate']].copy()
    disp.columns = ['担当者', 'チーム', '経験年数', 'コール数', '成約数', '成約率']
    disp['成約率'] = disp['成約率'].map('{:.1%}'.format)
    st.dataframe(disp.reset_index(drop=True), use_container_width=True)

# ===== 統計的有意性検定 =====
st.markdown('<div class="section-header">🧪 統計的有意性検定</div>', unsafe_allow_html=True)
st.caption("各インサイトが「偶然の偏り」ではなく統計的に有意かどうかを検証します（有意水準 α = 0.05）。")

stat_col1, stat_col2, stat_col3 = st.columns(3)

# Test 1: Spearman correlation — experience_years vs agent contract_rate
with stat_col1:
    if len(agent_stats) >= 5:
        rho, p_rho = stats.spearmanr(agent_stats['experience_years'], agent_stats['contract_rate'])
        sig1 = "有意差あり ✅" if p_rho < 0.05 else "有意差なし ⚠️"
        st.markdown(f"""
        <div class="insight-box">
        <b>経験年数 × 成約率<br>Spearman 順位相関</b><br><br>
        ρ = {rho:.3f}<br>
        p値 = {p_rho:.4f}<br>
        判定: <b>{sig1}</b><br><br>
        {"→ 経験年数と成約率の相関は統計的に裏付けられています。" if p_rho < 0.05 else "→ 現在の絞り込みでは有意差なし。フィルターを緩和してください。"}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("担当者が5名未満のため検定できません。フィルターを緩和してください。")

# Test 2: Chi-square — age_group independence vs contract result
with stat_col2:
    contingency_age = pd.crosstab(
        df_filtered['customer_age_group'],
        (df_filtered['call_result'] == '成約'),
    )
    if contingency_age.shape[0] >= 2 and contingency_age.shape[1] >= 2:
        chi2_age, p_chi2, dof_age, _ = stats.chi2_contingency(contingency_age)
        sig2 = "有意差あり ✅" if p_chi2 < 0.05 else "有意差なし ⚠️"
        st.markdown(f"""
        <div class="insight-box">
        <b>年齢層 × 成約率<br>カイ二乗検定</b><br><br>
        χ² = {chi2_age:.2f}（df = {dof_age}）<br>
        p値 = {p_chi2:.4f}<br>
        判定: <b>{sig2}</b><br><br>
        {"→ 年齢層によって成約率に有意な差があります。" if p_chi2 < 0.05 else "→ 現在の条件では年齢層間に有意差なし。"}
        </div>
        """, unsafe_allow_html=True)

# Test 3: Kruskal-Wallis — team differences in contract rate
with stat_col3:
    team_groups = [
        grp['is_contracted'].values
        for _, grp in df_filtered.groupby('team')
        if len(grp) >= 10
    ]
    if len(team_groups) >= 2:
        kw_stat, kw_p = stats.kruskal(*team_groups)
        sig3 = "有意差あり ✅" if kw_p < 0.05 else "有意差なし ⚠️"
        st.markdown(f"""
        <div class="insight-box">
        <b>チーム間 成約率差<br>Kruskal-Wallis 検定</b><br><br>
        H = {kw_stat:.3f}<br>
        p値 = {kw_p:.4f}<br>
        判定: <b>{sig3}</b><br><br>
        {"→ チーム間に統計的に有意な成約率の差があります。" if kw_p < 0.05 else "→ チーム間の差は統計的に有意ではありません。"}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("有効なチームが2つ未満のため検定できません。")

# ===== 時間帯分析 =====
st.markdown('<div class="section-header">⏰ 時間帯別 成約率・接触率</div>', unsafe_allow_html=True)

hourly = df_filtered.groupby('call_hour').agg(
    calls=('call_id', 'count'),
    contracts=('is_contracted', 'sum'),
    contacted=('is_contacted', 'sum'),
).reset_index()
hourly['contract_rate'] = hourly['contracts'] / hourly['calls']
hourly['contact_rate']  = hourly['contacted'] / hourly['calls']

best_hour  = hourly.loc[hourly['contract_rate'].idxmax(), 'call_hour']
best_rate  = hourly.loc[hourly['call_hour'] == best_hour, 'contract_rate'].values[0]
worst_hour = hourly.loc[hourly['contract_rate'].idxmin(), 'call_hour']
worst_rate = hourly.loc[hourly['call_hour'] == worst_hour, 'contract_rate'].values[0]

st.info(f"🏆 最も成約率が高い時間帯: **{best_hour}:00** ({best_rate:.1%})　／　最も低い時間帯: **{worst_hour}:00** ({worst_rate:.1%})")

fig, ax1 = plt.subplots(figsize=(14, 4.5))
fig.patch.set_facecolor('white')
ax1.set_facecolor('white')
bar_cols = [COLORS['success'] if h == best_hour else COLORS['primary'] for h in hourly['call_hour']]
ax1.bar(hourly['call_hour'], hourly['contract_rate'], color=bar_cols, alpha=0.8, width=0.6, label='Contract Rate')
ax1.set_xticks(hourly['call_hour'])
ax1.set_xticklabels([f'{h}:00' for h in hourly['call_hour']])
ax1.set_ylabel('成約率', color=COLORS['primary'])
ax1.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
ax2 = ax1.twinx()
ax2.plot(hourly['call_hour'], hourly['contact_rate'], 'o-',
         color=COLORS['warning'], linewidth=2.5, markersize=7, label='Contact Rate')
ax2.set_ylabel('接触率', color=COLORS['warning'])
ax2.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
ax1.set_title('時間帯別 成約率 / 接触率', fontweight='bold')
plt.tight_layout()
st.pyplot(fig)
plt.close()

# 時間帯インサイト（フィルター連動）
best_hour_calls  = hourly.loc[hourly['call_hour'] == best_hour, 'calls'].values[0]
worst_hour_calls = hourly.loc[hourly['call_hour'] == worst_hour, 'calls'].values[0]
total_hour_calls = hourly['calls'].sum()
pct_best  = best_hour_calls / total_hour_calls
potential_gain = int((best_rate - hourly['contract_rate'].mean()) * total_hour_calls)

st.markdown(f"""
<div class="insight-box">
💡 <b>現在の条件でのコールタイミング分析</b><br><br>
🟢 最高成約率 <b>{best_hour}:00台</b>（{best_rate:.1%}）へのコールは全体の <b>{pct_best:.1%}</b> のみ。<br>
🔴 最低成約率 <b>{worst_hour}:00台</b>（{worst_rate:.1%}）には <b>{worst_hour_calls:,}件</b> が集中。<br>
→ 最低時間帯のコールを最高時間帯に移すだけで、月間約 <b>{potential_gain}件</b> の成約増が試算されます。
コールスケジュールの見直しを最優先で検討することを推奨します。
</div>
""", unsafe_allow_html=True)

# ===== 顧客属性クロス分析 =====
st.markdown('<div class="section-header">👥 顧客属性クロス分析（年齢 × 性別 × 成約率）</div>', unsafe_allow_html=True)

age_order_disp = [a for a in age_order if a in df_filtered['customer_age_group'].unique()]
cross = df_filtered.groupby(['customer_age_group', 'customer_gender']).agg(
    calls=('call_id', 'count'),
    contracts=('is_contracted', 'sum'),
).reset_index()
cross['contract_rate'] = cross['contracts'] / cross['calls']

col_cross1, col_cross2 = st.columns(2)

with col_cross1:
    # ヒートマップ
    pivot = cross.pivot(index='customer_age_group', columns='customer_gender', values='contract_rate')
    pivot = pivot.reindex([a for a in age_order if a in pivot.index])
    fig, ax = plt.subplots(figsize=(6, 4))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    im = ax.imshow(pivot.values, cmap='Blues', aspect='auto', vmin=0)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f'{val:.1%}', ha='center', va='center', fontsize=11, fontweight='bold',
                        color='white' if val > pivot.values[~np.isnan(pivot.values)].mean() else 'black')
    plt.colorbar(im, ax=ax, format=matplotlib.ticker.PercentFormatter(1.0))
    ax.set_title('年齢 × 性別 成約率ヒートマップ', fontweight='bold')
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

with col_cross2:
    # 年齢層別・性別グループ棒グラフ
    genders = cross['customer_gender'].unique()
    x = np.arange(len(age_order_disp))
    width = 0.35
    fig, ax = plt.subplots(figsize=(6, 4))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    gender_colors = [COLORS['primary'], COLORS['danger'], COLORS['neutral']]
    for i, gender in enumerate(sorted(genders)):
        vals = []
        for age in age_order_disp:
            row = cross[(cross['customer_age_group'] == age) & (cross['customer_gender'] == gender)]
            vals.append(row['contract_rate'].values[0] if len(row) > 0 else 0)
        offset = (i - len(genders) / 2 + 0.5) * width
        ax.bar(x + offset, vals, width, label=gender,
               color=gender_colors[i % len(gender_colors)], alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(age_order_disp)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_title('年齢層・性別ごとの成約率', fontweight='bold')
    ax.legend()
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

# 顧客属性インサイト（フィルター連動）
best_segment  = cross.loc[cross['contract_rate'].idxmax()]
worst_segment = cross.loc[cross['contract_rate'].idxmin()]
rate_gap = best_segment['contract_rate'] - worst_segment['contract_rate']
top3 = cross.nlargest(3, 'contract_rate')

st.markdown(f"""
<div class="insight-box">
💡 <b>現在の条件での顧客セグメント分析</b><br><br>
🏆 最高成約セグメント：<b>{best_segment['customer_age_group']} × {best_segment['customer_gender']}</b>（{best_segment['contract_rate']:.1%}）<br>
⚠️ 最低成約セグメント：<b>{worst_segment['customer_age_group']} × {worst_segment['customer_gender']}</b>（{worst_segment['contract_rate']:.1%}）<br>
📊 両者の差は <b>{rate_gap:.1%}ポイント</b>。<br>
→ コールリストを上位3セグメント（{'・'.join([f"{r['customer_age_group']}/{r['customer_gender']}" for _, r in top3.iterrows()])}）に絞るだけで
成約率の大幅改善が期待できます。
</div>
""", unsafe_allow_html=True)

with st.expander("📋 顧客属性クロス集計テーブル"):
    disp_cross = cross.copy()
    disp_cross = disp_cross.rename(columns={
        'customer_age_group': '年齢層',
        'customer_gender': '性別',
        'calls': 'コール数',
        'contracts': '成約数',
        'contract_rate': '成約率',
    })[['年齢層', '性別', 'コール数', '成約数', '成約率']]
    styled = (
        disp_cross.reset_index(drop=True)
        .style
        .bar(subset=['コール数'], color='#BFDBFE')
        .bar(subset=['成約数'], color='#BBF7D0')
        .bar(subset=['成約率'], color='#FDE68A', vmin=0, vmax=1)
        .format({'成約率': '{:.1%}'})
    )
    st.dataframe(styled, use_container_width=True)

# ===== 月次トレンド =====
st.markdown('<div class="section-header">📈 月次トレンド</div>', unsafe_allow_html=True)

monthly = df_filtered.groupby('call_month').agg(
    calls=('call_id', 'count'),
    contracts=('is_contracted', 'sum'),
    contract_rate=('is_contracted', 'mean'),
).reset_index().sort_values('call_month')

col_a, col_b = st.columns(2)
months = range(len(monthly))
labels = [m[5:] + '月' for m in monthly['call_month']]

with col_a:
    fig, ax = plt.subplots(figsize=(7, 4))
    fig.patch.set_facecolor('white'); ax.set_facecolor('white')
    ax.bar(months, monthly['calls'], color=COLORS['primary'], alpha=0.6, label='コール数')
    ax.bar(months, monthly['contracts'], color=COLORS['success'], alpha=0.9, label='成約数')
    ax.set_xticks(months); ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_title('月次 コール数 / 成約数', fontweight='bold')
    ax.legend()
    plt.tight_layout(); st.pyplot(fig); plt.close()

with col_b:
    fig, ax = plt.subplots(figsize=(7, 4))
    fig.patch.set_facecolor('white'); ax.set_facecolor('white')
    ax.plot(months, monthly['contract_rate'], 'o-', color=COLORS['warning'], linewidth=2.5, markersize=8)
    ax.fill_between(months, monthly['contract_rate'], alpha=0.15, color=COLORS['warning'])
    avg = monthly['contract_rate'].mean()
    ax.axhline(avg, color='red', linestyle='--', linewidth=1.5, label=f'平均 {avg:.1%}')
    ax.set_xticks(months); ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_title('月次 成約率トレンド', fontweight='bold')
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.legend()
    plt.tight_layout(); st.pyplot(fig); plt.close()

# 月次インサイト（フィルター連動）
best_month_row   = monthly.loc[monthly['contract_rate'].idxmax()]
worst_month_row  = monthly.loc[monthly['contract_rate'].idxmin()]
monthly_gap      = best_month_row['contract_rate'] - worst_month_row['contract_rate']
avg_monthly_calls = monthly['calls'].mean()
potential_monthly = int(monthly_gap * avg_monthly_calls)
above_avg_months = monthly[monthly['contract_rate'] > monthly['contract_rate'].mean()]

st.markdown(f"""
<div class="insight-box">
💡 <b>現在の条件での月次トレンド分析</b><br><br>
📈 最高月：<b>{best_month_row['call_month'][5:]}月</b>（{best_month_row['contract_rate']:.1%}）
／ 最低月：<b>{worst_month_row['call_month'][5:]}月</b>（{worst_month_row['contract_rate']:.1%}）<br>
📊 月間最大差は <b>{monthly_gap:.1%}ポイント</b>（月平均{avg_monthly_calls:.0f}件なら約{potential_monthly}件の差）。<br>
🗓️ 平均以上の月は <b>{'・'.join([m[5:]+'月' for m in above_avg_months['call_month']])}（{len(above_avg_months)}ヶ月）</b>。<br>
→ これらの月にコール数・人員を集中させることで年間成約数を最大化できます。
</div>
""", unsafe_allow_html=True)

# ===== 商品別 =====
st.markdown('<div class="section-header">🛡️ 商品別 成約実績</div>', unsafe_allow_html=True)

prod_stats = df_filtered[df_filtered['is_contracted'] == 1].groupby('product_name').agg(
    contracts=('call_id', 'count'),
    monthly_premium=('monthly_premium', 'first'),
).reset_index()
prod_stats['estimated_revenue'] = prod_stats['contracts'] * prod_stats['monthly_premium'] * 12
prod_stats = prod_stats.sort_values('contracts', ascending=True)

fig, axes = plt.subplots(1, 2, figsize=(14, 4))
fig.patch.set_facecolor('white')
pal = [COLORS['primary'], COLORS['success'], COLORS['warning'], COLORS['danger'], COLORS['neutral'], '#7C3AED']
for ax_i, (col, label) in zip(axes, [('contracts', '成約件数'), ('estimated_revenue', '推定年間収益（円）')]):
    ax_i.set_facecolor('white')
    vals = prod_stats[col]
    if col == 'estimated_revenue':
        vals = vals / 1e6
        label = '推定年間収益（百万円）'
    ax_i.barh(prod_stats['product_name'], vals, color=pal[:len(prod_stats)])
    ax_i.set_xlabel(label)
    ax_i.set_title(f'商品別 {label}', fontweight='bold')
plt.tight_layout()
st.pyplot(fig)
plt.close()

# 商品別インサイト（フィルター連動）
top_rev_product  = prod_stats.loc[prod_stats['estimated_revenue'].idxmax()]
top_cnt_product  = prod_stats.loc[prod_stats['contracts'].idxmax()]
total_revenue    = prod_stats['estimated_revenue'].sum()
top_rev_share    = top_rev_product['estimated_revenue'] / total_revenue

st.markdown(f"""
<div class="insight-box">
💡 <b>現在の条件での商品別分析</b><br><br>
💰 収益最大商品：<b>{top_rev_product['product_name']}</b>（推定年間 {top_rev_product['estimated_revenue']/1e6:.1f}百万円、全体の{top_rev_share:.1%}）<br>
📦 成約件数最大：<b>{top_cnt_product['product_name']}</b>（{int(top_cnt_product['contracts'])}件）<br>
→ 収益貢献度の高い <b>{top_rev_product['product_name']}</b> を重点商品に指定し、
担当者全員が自信を持って提案できるよう研修リソースを優先配置することを推奨します。
</div>
""", unsafe_allow_html=True)

# ===== 成約予測モデル（Random Forest） =====
st.markdown('<div class="section-header">🤖 成約予測モデル（Random Forest）</div>', unsafe_allow_html=True)
st.caption("担当者経験年数・コール時間帯・顧客属性から成約確率を予測します。モデルは全データで学習し、5-Fold CVで評価します。")

_age_map = {'20代': 0, '30代': 1, '40代': 2, '50代': 3, '60代以上': 4}
_gender_map = {'男性': 0, '女性': 1}

_ml_df = df.copy()
_ml_df['age_encoded'] = _ml_df['customer_age_group'].map(_age_map)
_ml_df['gender_encoded'] = _ml_df['customer_gender'].map(_gender_map)
_ml_df = _ml_df.dropna(subset=['age_encoded', 'gender_encoded', 'experience_years'])

_feature_names = ['コール時間帯', '経験年数', '顧客年齢層', '顧客性別']
_X = _ml_df[['call_hour', 'experience_years', 'age_encoded', 'gender_encoded']].values
_y = _ml_df['is_contracted'].values

_rf = RandomForestClassifier(n_estimators=200, random_state=42, class_weight='balanced')
_cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
_auc_scores = cross_val_score(_rf, _X, _y, cv=_cv, scoring='roc_auc')
_rf.fit(_X, _y)

col_ml1, col_ml2 = st.columns(2)

with col_ml1:
    _importances = _rf.feature_importances_
    _sorted_idx = np.argsort(_importances)
    fig, ax = plt.subplots(figsize=(6, 3.5))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    _bars = ax.barh(
        [_feature_names[i] for i in _sorted_idx],
        _importances[_sorted_idx],
        color=COLORS['primary'], alpha=0.85,
    )
    for bar, val in zip(_bars, _importances[_sorted_idx]):
        ax.text(val + 0.002, bar.get_y() + bar.get_height() / 2,
                f'{val:.3f}', va='center', fontsize=9)
    ax.set_title('特徴量重要度 (Feature Importance)', fontweight='bold')
    ax.set_xlabel('Importance')
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

with col_ml2:
    _mean_auc = _auc_scores.mean()
    _std_auc = _auc_scores.std()
    _top2_features = [_feature_names[i] for i in np.argsort(_importances)[::-1][:2]]
    st.markdown(f"""
    <div class="insight-box">
    <b>モデル性能（5-Fold Cross Validation）</b><br><br>
    📊 AUC-ROC: <b>{_mean_auc:.3f} ± {_std_auc:.3f}</b><br>
    {'🟢 良好（ランダム予測 0.5 を有意に上回る）' if _mean_auc >= 0.60 else '🟡 改善余地あり'}<br><br>
    📌 重要度上位: <b>{"・".join(_top2_features)}</b><br><br>
    → 特徴量重要度から、これらの要因が成約に最も影響することが示されます。
    コール戦略立案時の優先変数として活用できます。
    </div>
    """, unsafe_allow_html=True)

# Segment prediction table
st.markdown("**📋 セグメント別 予測成約確率（最高成約率時間帯・平均経験年数の条件下）**")
_avg_exp = _ml_df['experience_years'].mean()

_pred_rows = []
for _age_label, _age_enc in _age_map.items():
    for _gender_label, _gender_enc in _gender_map.items():
        _prob = _rf.predict_proba([[best_hour, _avg_exp, _age_enc, _gender_enc]])[0][1]
        _pred_rows.append({
            '年齢層': _age_label,
            '性別': _gender_label,
            '予測成約確率': _prob,
        })

_pred_df = pd.DataFrame(_pred_rows).sort_values('予測成約確率', ascending=False).reset_index(drop=True)
_pred_df['推奨優先度'] = [
    '🔴 最優先' if i < 2 else ('🟡 中優先' if i < 5 else '⚪ 低優先')
    for i in range(len(_pred_df))
]
_pred_df['予測成約確率'] = _pred_df['予測成約確率'].map('{:.1%}'.format)
st.dataframe(_pred_df, use_container_width=True)

st.markdown(f"""
<div class="insight-box">
💡 <b>コール戦略への応用</b><br><br>
上表は「{best_hour}:00台にコール・経験{_avg_exp:.1f}年の担当者が対応」という条件下での
セグメント別予測成約確率です（モデルはダミーデータで学習）。<br>
→ 確率上位セグメントをコールリスト優先度として組み込むことで、同じコール数でより多くの成約が期待できます。<br>
→ 実業務では実データで再学習し、定期的にモデルを更新することを推奨します。
</div>
""", unsafe_allow_html=True)

st.markdown("---")
st.caption("📌 このダッシュボードはダミーデータを使用したポートフォリオ作品です。")
