"""
generate_images.py
==================
README用スクリーンショット画像を生成するスクリプト。
app.py と同一フォント・スタイル・データを使用し、notebooks/ に保存する。

実行方法:
    python generate_images.py
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker
import matplotlib.font_manager as fm
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold

# ===== フォント設定（app.py と完全同一） =====
_font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'IPAGothic.ttf')
if os.path.exists(_font_path):
    fm.fontManager.addfont(_font_path)
    _prop = fm.FontProperties(fname=_font_path)
    matplotlib.rcParams['font.family'] = _prop.get_name()
matplotlib.rcParams['axes.unicode_minus'] = False

COLORS = {
    'primary': '#2563EB', 'success': '#16A34A',
    'warning': '#D97706', 'danger': '#DC2626', 'neutral': '#6B7280',
}
TEAM_COLORS = {'東京チーム': '#2563EB', '大阪チーム': '#16A34A', '名古屋チーム': '#D97706'}
OUT_DIR = 'notebooks'

# ===== データ読み込み =====
calls    = pd.read_csv('data/calls.csv', parse_dates=['call_date'])
agents   = pd.read_csv('data/agents.csv')
products = pd.read_csv('data/products.csv')

df = calls.merge(agents, on='agent_id', how='left').merge(products, on='product_id', how='left')
df['is_contracted'] = (df['call_result'] == '成約').astype(int)
df['is_contacted']  = (df['call_result'] != '不在').astype(int)

print(f'データ読み込み完了: {len(df):,} 件')

# ===== 1. KPI サマリー（Streamlit スタイル） =====
total_calls      = len(df)
total_contracts  = df['is_contracted'].sum()
contract_rate    = df['is_contracted'].mean()
contact_rate     = df['is_contacted'].mean()

fig, axes = plt.subplots(1, 4, figsize=(14, 3.5))
fig.patch.set_facecolor('#F0F2F6')  # Streamlit のデフォルト背景色

kpis = [
    ('総コール数', f'{total_calls:,}', COLORS['primary']),
    ('成約数', f'{total_contracts:,}', COLORS['success']),
    ('成約率', f'{contract_rate:.1%}', COLORS['warning']),
    ('接触率', f'{contact_rate:.1%}', COLORS['neutral']),
]

for ax, (label, value, color) in zip(axes, kpis):
    ax.set_facecolor('#F0F2F6')
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks([]); ax.set_yticks([])

    # シャドウ（ずらした薄いグレーの角丸矩形）
    ax.add_patch(mpatches.FancyBboxPatch(
        (0.055, 0.03), 0.9, 0.9,
        boxstyle='round,pad=0.04', linewidth=0,
        facecolor='#D1D5DB', transform=ax.transAxes, zorder=1))

    # 白カード（枠線なし）
    ax.add_patch(mpatches.FancyBboxPatch(
        (0.05, 0.08), 0.9, 0.9,
        boxstyle='round,pad=0.04', linewidth=0,
        facecolor='white', transform=ax.transAxes, zorder=2))

    # 数値（大・太・カラー）
    ax.text(0.5, 0.63, value, ha='center', va='center',
            fontsize=28, fontweight='bold', color=color,
            transform=ax.transAxes, zorder=3)

    # ラベル（小・グレー）
    ax.text(0.5, 0.28, label, ha='center', va='center',
            fontsize=11, color='#6B7280',
            transform=ax.transAxes, zorder=3)

plt.tight_layout(pad=1.2)
fig.savefig(f'{OUT_DIR}/kpi_summary.png', dpi=150, bbox_inches='tight')
plt.close()
print('1/7 kpi_summary.png 保存')

# ===== 2. 担当者別パフォーマンス =====
agent_stats = df.groupby(['agent_id', 'name', 'team', 'experience_years']).agg(
    calls=('call_id', 'count'),
    contracts=('is_contracted', 'sum'),
).reset_index()
agent_stats['contract_rate'] = agent_stats['contracts'] / agent_stats['calls']
agent_stats = agent_stats.sort_values('contract_rate', ascending=False)

fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
fig.patch.set_facecolor('white')

# 左: 成約率ランキング
ax = axes[0]
ax.set_facecolor('white')
colors = [TEAM_COLORS.get(t, COLORS['neutral']) for t in agent_stats['team']]
bars = ax.barh(agent_stats['name'], agent_stats['contract_rate'], color=colors, alpha=0.85)
ax.axvline(agent_stats['contract_rate'].mean(), color='red', linestyle='--', linewidth=1.5, label='平均')
for bar, val in zip(bars, agent_stats['contract_rate']):
    ax.text(val + 0.002, bar.get_y() + bar.get_height() / 2, f'{val:.1%}', va='center', fontsize=9)
patches = [mpatches.Patch(color=c, label=t) for t, c in TEAM_COLORS.items()]
ax.legend(handles=patches + [plt.Line2D([0], [0], color='red', linestyle='--', label='平均')], fontsize=8)
ax.set_title('成約率ランキング', fontweight='bold')
ax.set_xlabel('成約率')
ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))

# 右: 経験年数 vs 成約率 散布図
ax2 = axes[1]
ax2.set_facecolor('white')
for team, grp in agent_stats.groupby('team'):
    ax2.scatter(grp['experience_years'], grp['contract_rate'],
                color=TEAM_COLORS.get(team, COLORS['neutral']),
                s=grp['calls'] * 0.3, alpha=0.8, label=team)
    for _, row in grp.iterrows():
        ax2.annotate(row['name'].split()[0],
                     (row['experience_years'], row['contract_rate']),
                     textcoords='offset points', xytext=(5, 3), fontsize=8)
x = agent_stats['experience_years'].values
y = agent_stats['contract_rate'].values
if len(x) > 1:
    z = np.polyfit(x, y, 1)
    xl = np.linspace(x.min(), x.max(), 100)
    ax2.plot(xl, np.poly1d(z)(xl), 'r--', linewidth=1.5, alpha=0.7, label='トレンド')
ax2.set_xlabel('経験年数')
ax2.set_ylabel('成約率')
ax2.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
ax2.set_title('経験年数 vs 成約率\n（バブルサイズ = コール数）', fontweight='bold')
ax2.legend(fontsize=8)

plt.tight_layout()
fig.savefig(f'{OUT_DIR}/agent_performance.png', dpi=150, bbox_inches='tight')
plt.close()
print('2/7 agent_performance.png 保存')

# ===== 3. 時間帯別 成約率・接触率 =====
hourly = df.groupby('call_hour').agg(
    calls=('call_id', 'count'),
    contracts=('is_contracted', 'sum'),
    contacted=('is_contacted', 'sum'),
).reset_index()
hourly['contract_rate'] = hourly['contracts'] / hourly['calls']
hourly['contact_rate']  = hourly['contacted'] / hourly['calls']
best_hour = hourly.loc[hourly['contract_rate'].idxmax(), 'call_hour']

fig, ax1 = plt.subplots(figsize=(14, 4.5))
fig.patch.set_facecolor('white')
ax1.set_facecolor('white')

bar_cols = [COLORS['success'] if h == best_hour else COLORS['primary'] for h in hourly['call_hour']]
ax1.bar(hourly['call_hour'], hourly['contract_rate'], color=bar_cols, alpha=0.8, width=0.6, label='成約率')
ax1.set_xticks(hourly['call_hour'])
ax1.set_xticklabels([f'{h}:00' for h in hourly['call_hour']])
ax1.set_ylabel('成約率', color=COLORS['primary'])
ax1.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))

ax2 = ax1.twinx()
ax2.plot(hourly['call_hour'], hourly['contact_rate'], 'o-',
         color=COLORS['warning'], linewidth=2.5, markersize=7, label='接触率')
ax2.set_ylabel('接触率', color=COLORS['warning'])
ax2.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))

best_rate = hourly.loc[hourly['call_hour'] == best_hour, 'contract_rate'].values[0]
ax1.axvline(best_hour, color='red', linestyle='--', alpha=0.5)
ax1.text(best_hour + 0.1, ax1.get_ylim()[1] * 0.95, f'最高: {best_hour}:00 ({best_rate:.1%})',
         color='red', fontsize=10, fontweight='bold')

ax1.legend(['成約率（棒グラフ）'], loc='upper left', fontsize=9)
ax2.legend(['接触率'], loc='upper right', fontsize=9)
plt.title('時間帯別 成約率 / 接触率', fontweight='bold', fontsize=13)
plt.tight_layout()
fig.savefig(f'{OUT_DIR}/hourly_analysis.png', dpi=150, bbox_inches='tight')
plt.close()
print('3/7 hourly_analysis.png 保存')

# ===== 4. 顧客属性クロス分析（年齢 × 性別） =====
age_order = ['20代', '30代', '40代', '50代', '60代以上']
cross = df.groupby(['customer_age_group', 'customer_gender']).agg(
    calls=('call_id', 'count'),
    contracts=('is_contracted', 'sum'),
).reset_index()
cross['contract_rate'] = cross['contracts'] / cross['calls']

age_order_disp = [a for a in age_order if a in cross['customer_age_group'].unique()]

fig, axes = plt.subplots(1, 2, figsize=(14, 4))
fig.patch.set_facecolor('white')

# 左: ヒートマップ
ax = axes[0]
ax.set_facecolor('white')
pivot = cross.pivot(index='customer_age_group', columns='customer_gender', values='contract_rate')
pivot = pivot.reindex([a for a in age_order if a in pivot.index])
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

# 右: グループ棒グラフ
ax2 = axes[1]
ax2.set_facecolor('white')
genders = sorted(cross['customer_gender'].unique())
x = np.arange(len(age_order_disp))
width = 0.35
gender_colors = [COLORS['primary'], COLORS['danger'], COLORS['neutral']]
for i, gender in enumerate(genders):
    vals = []
    for age in age_order_disp:
        row = cross[(cross['customer_age_group'] == age) & (cross['customer_gender'] == gender)]
        vals.append(row['contract_rate'].values[0] if len(row) > 0 else 0)
    offset = (i - len(genders) / 2 + 0.5) * width
    ax2.bar(x + offset, vals, width, label=gender,
            color=gender_colors[i % len(gender_colors)], alpha=0.85)
ax2.set_xticks(x)
ax2.set_xticklabels(age_order_disp)
ax2.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
ax2.set_title('年齢層・性別ごとの成約率', fontweight='bold')
ax2.legend()

plt.tight_layout()
fig.savefig(f'{OUT_DIR}/customer_analysis.png', dpi=150, bbox_inches='tight')
plt.close()
print('4/7 customer_analysis.png 保存')

# ===== 5. 月次トレンド =====
monthly = df.groupby('call_month').agg(
    calls=('call_id', 'count'),
    contracts=('is_contracted', 'sum'),
    contract_rate=('is_contracted', 'mean'),
).reset_index().sort_values('call_month')

months = range(len(monthly))
labels = [m[5:] + '月' for m in monthly['call_month']]

fig, axes = plt.subplots(1, 2, figsize=(14, 4))
fig.patch.set_facecolor('white')

# 左: コール数/成約数
ax = axes[0]
ax.set_facecolor('white')
ax.bar(months, monthly['calls'], color=COLORS['primary'], alpha=0.6, label='コール数')
ax.bar(months, monthly['contracts'], color=COLORS['success'], alpha=0.9, label='成約数')
ax.set_xticks(months)
ax.set_xticklabels(labels, rotation=45, ha='right')
ax.set_title('月次 コール数 / 成約数', fontweight='bold')
ax.legend()

# 右: 成約率トレンド
ax2 = axes[1]
ax2.set_facecolor('white')
ax2.plot(months, monthly['contract_rate'], 'o-', color=COLORS['warning'], linewidth=2.5, markersize=8)
ax2.fill_between(months, monthly['contract_rate'], alpha=0.15, color=COLORS['warning'])
avg = monthly['contract_rate'].mean()
ax2.axhline(avg, color='red', linestyle='--', linewidth=1.5, label=f'平均 {avg:.1%}')
ax2.set_xticks(months)
ax2.set_xticklabels(labels, rotation=45, ha='right')
ax2.set_title('月次 成約率トレンド', fontweight='bold')
ax2.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
ax2.legend()

plt.tight_layout()
fig.savefig(f'{OUT_DIR}/monthly_trend.png', dpi=150, bbox_inches='tight')
plt.close()
print('5/7 monthly_trend.png 保存')

# ===== 6. 商品別 成約実績 =====
prod_stats = df[df['is_contracted'] == 1].groupby('product_name').agg(
    contracts=('call_id', 'count'),
    monthly_premium=('monthly_premium', 'first'),
).reset_index()
prod_stats['estimated_revenue'] = prod_stats['contracts'] * prod_stats['monthly_premium'] * 12
prod_stats = prod_stats.sort_values('contracts', ascending=True)

pal = [COLORS['primary'], COLORS['success'], COLORS['warning'], COLORS['danger'], COLORS['neutral'], '#7C3AED']

fig, axes = plt.subplots(1, 2, figsize=(14, 4))
fig.patch.set_facecolor('white')

for ax_i, (col, label) in zip(axes, [('contracts', '成約件数'), ('estimated_revenue', '推定年間収益（円）')]):
    ax_i.set_facecolor('white')
    vals = prod_stats[col].copy()
    if col == 'estimated_revenue':
        vals = vals / 1e6
        label = '推定年間収益（百万円）'
    bars = ax_i.barh(prod_stats['product_name'], vals, color=pal[:len(prod_stats)])
    for bar, val in zip(bars, vals):
        suffix = '件' if col == 'contracts' else 'M'
        ax_i.text(val + vals.max() * 0.01, bar.get_y() + bar.get_height() / 2,
                  f'{val:.0f}{suffix}' if col == 'contracts' else f'¥{val:.1f}M',
                  va='center', fontsize=9)
    ax_i.set_xlabel(label)
    ax_i.set_title(f'商品別 {label}', fontweight='bold')

plt.tight_layout()
fig.savefig(f'{OUT_DIR}/product_analysis.png', dpi=150, bbox_inches='tight')
plt.close()
print('6/7 product_analysis.png 保存')

# ===== 7. ML 特徴量重要度 =====
age_map    = {'20代': 0, '30代': 1, '40代': 2, '50代': 3, '60代以上': 4}
gender_map = {'男性': 0, '女性': 1}

ml_df = df.copy()
ml_df['age_encoded']    = ml_df['customer_age_group'].map(age_map)
ml_df['gender_encoded'] = ml_df['customer_gender'].map(gender_map)
ml_df = ml_df.dropna(subset=['age_encoded', 'gender_encoded', 'experience_years'])

feature_names = ['コール時間帯', '経験年数', '顧客年齢層', '顧客性別']
X = ml_df[['call_hour', 'experience_years', 'age_encoded', 'gender_encoded']].values
y = ml_df['is_contracted'].values

rf = RandomForestClassifier(n_estimators=200, random_state=42, class_weight='balanced')
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
auc_scores = cross_val_score(rf, X, y, cv=cv, scoring='roc_auc')
rf.fit(X, y)

importances = rf.feature_importances_
sorted_idx  = np.argsort(importances)
mean_auc    = auc_scores.mean()
std_auc     = auc_scores.std()

fig, ax = plt.subplots(figsize=(8, 4))
fig.patch.set_facecolor('white')
ax.set_facecolor('white')
bars = ax.barh([feature_names[i] for i in sorted_idx], importances[sorted_idx],
               color=COLORS['primary'], alpha=0.85)
for bar, val in zip(bars, importances[sorted_idx]):
    ax.text(val + 0.002, bar.get_y() + bar.get_height() / 2,
            f'{val:.3f}', va='center', fontsize=10)
ax.set_title(f'特徴量重要度（Random Forest）\nAUC-ROC: {mean_auc:.3f} ± {std_auc:.3f}（5-Fold CV）',
             fontweight='bold')
ax.set_xlabel('Importance')
plt.tight_layout()
fig.savefig(f'{OUT_DIR}/ml_feature_importance.png', dpi=150, bbox_inches='tight')
plt.close()
print('7/7 ml_feature_importance.png 保存')

print('\n完了: 全7枚を notebooks/ に保存しました。')
