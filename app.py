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
all_teams = df['team'].dropna().unique().tolist()
selected_teams = st.sidebar.multiselect("チーム", all_teams, default=all_teams)

# 期間フィルター
min_date = df['call_date'].min().date()
max_date = df['call_date'].max().date()
date_range = st.sidebar.date_input("期間", value=(min_date, max_date), min_value=min_date, max_value=max_date)

if len(date_range) == 2:
    df_filtered = df[
        (df['team'].isin(selected_teams)) &
        (df['call_date'].dt.date >= date_range[0]) &
        (df['call_date'].dt.date <= date_range[1])
    ]
else:
    df_filtered = df[df['team'].isin(selected_teams)]


# ===== メインコンテンツ =====
st.title("📊 生命保険 アウトバウンドコール 営業成績ダッシュボード")
st.caption(f"分析期間: {df_filtered['call_date'].min().strftime('%Y/%m/%d')} 〜 {df_filtered['call_date'].max().strftime('%Y/%m/%d')}  |  対象チーム: {', '.join(selected_teams)}")

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
    ax.set_ylabel('Contract Rate')
    ax.set_title('経験年数 vs 成約率\n(バブルサイズ = コール数)', fontweight='bold')
    ax.legend(fontsize=8)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

# 詳細テーブル
with st.expander("📋 担当者詳細データを表示"):
    disp = agent_stats[['name', 'team', 'experience_years', 'calls', 'contracts', 'contract_rate']].copy()
    disp.columns = ['担当者', 'チーム', '経験年数', 'コール数', '成約数', '成約率']
    disp['成約率'] = disp['成約率'].map('{:.1%}'.format)
    st.dataframe(disp.reset_index(drop=True), use_container_width=True)

# ===== 時間帯分析 =====
st.markdown('<div class="section-header">⏰ 時間帯別 成約率・接触率</div>', unsafe_allow_html=True)

hourly = df_filtered.groupby('call_hour').agg(
    calls=('call_id', 'count'),
    contracts=('is_contracted', 'sum'),
    contacted=('is_contacted', 'sum'),
).reset_index()
hourly['contract_rate'] = hourly['contracts'] / hourly['calls']
hourly['contact_rate']  = hourly['contacted'] / hourly['calls']

best_hour = hourly.loc[hourly['contract_rate'].idxmax(), 'call_hour']
st.info(f"🏆 最も成約率が高い時間帯: **{best_hour}:00** ({hourly.loc[hourly['call_hour']==best_hour, 'contract_rate'].values[0]:.1%})")

fig, ax1 = plt.subplots(figsize=(14, 4.5))
fig.patch.set_facecolor('white')
ax1.set_facecolor('white')
bar_cols = [COLORS['success'] if h == best_hour else COLORS['primary'] for h in hourly['call_hour']]
ax1.bar(hourly['call_hour'], hourly['contract_rate'], color=bar_cols, alpha=0.8, width=0.6, label='Contract Rate')
ax1.set_xticks(hourly['call_hour'])
ax1.set_xticklabels([f'{h}:00' for h in hourly['call_hour']])
ax1.set_ylabel('Contract Rate', color=COLORS['primary'])
ax2 = ax1.twinx()
ax2.plot(hourly['call_hour'], hourly['contact_rate'], 'o-',
         color=COLORS['warning'], linewidth=2.5, markersize=7, label='Contact Rate')
ax2.set_ylabel('Contact Rate', color=COLORS['warning'])
ax1.set_title('時間帯別 成約率 / 接触率', fontweight='bold')
plt.tight_layout()
st.pyplot(fig)
plt.close()

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

st.markdown("---")
st.caption("📌 このダッシュボードはダミーデータを使用したポートフォリオ作品です。")
