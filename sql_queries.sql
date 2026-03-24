-- ============================================================
-- 生命保険 アウトバウンドコール 営業成績分析 SQL集
-- ============================================================
-- 前提テーブル:
--   calls    (call_id, agent_id, product_id, call_date, call_hour, call_month,
--             call_result, customer_age_group, customer_gender)
--   agents   (agent_id, name, team, experience_years)
--   products (product_id, product_name, category, monthly_premium)
-- ============================================================


-- ============================================================
-- 1. KPIサマリー
-- ============================================================
SELECT
    COUNT(*)                                                  AS total_calls,
    SUM(CASE WHEN call_result = '成約' THEN 1 ELSE 0 END)    AS total_contracts,
    AVG(CASE WHEN call_result = '成約' THEN 1.0 ELSE 0 END)  AS contract_rate,
    AVG(CASE WHEN call_result != '不在' THEN 1.0 ELSE 0 END) AS contact_rate
FROM calls;


-- ============================================================
-- 2. 担当者別パフォーマンス（成約率ランキング）
-- ============================================================
SELECT
    a.agent_id,
    a.name,
    a.team,
    a.experience_years,
    COUNT(*)                                                  AS calls,
    SUM(CASE WHEN c.call_result = '成約' THEN 1 ELSE 0 END)  AS contracts,
    AVG(CASE WHEN c.call_result = '成約' THEN 1.0 ELSE 0 END) AS contract_rate
FROM calls c
JOIN agents a ON c.agent_id = a.agent_id
GROUP BY a.agent_id, a.name, a.team, a.experience_years
ORDER BY contract_rate DESC;


-- ============================================================
-- 3. 時間帯別 成約率・接触率
-- ============================================================
SELECT
    call_hour,
    COUNT(*)                                                  AS calls,
    SUM(CASE WHEN call_result = '成約' THEN 1 ELSE 0 END)    AS contracts,
    AVG(CASE WHEN call_result = '成約' THEN 1.0 ELSE 0 END)  AS contract_rate,
    AVG(CASE WHEN call_result != '不在' THEN 1.0 ELSE 0 END) AS contact_rate
FROM calls
GROUP BY call_hour
ORDER BY call_hour;


-- ============================================================
-- 4. 顧客属性クロス分析（年齢 × 性別 × 成約率）
-- ============================================================
SELECT
    customer_age_group,
    customer_gender,
    COUNT(*)                                                  AS calls,
    SUM(CASE WHEN call_result = '成約' THEN 1 ELSE 0 END)    AS contracts,
    AVG(CASE WHEN call_result = '成約' THEN 1.0 ELSE 0 END)  AS contract_rate
FROM calls
GROUP BY customer_age_group, customer_gender
ORDER BY contract_rate DESC;


-- ============================================================
-- 5. 商品別 成約件数・推定年間収益
-- ============================================================
SELECT
    p.product_name,
    p.category,
    p.monthly_premium,
    COUNT(c.call_id)                                          AS contracts,
    COUNT(c.call_id) * p.monthly_premium * 12                AS estimated_annual_revenue
FROM calls c
JOIN products p ON c.product_id = p.product_id
WHERE c.call_result = '成約'
GROUP BY p.product_name, p.category, p.monthly_premium
ORDER BY estimated_annual_revenue DESC;


-- ============================================================
-- 6. 月次トレンド（成約率の推移）
-- ============================================================
SELECT
    call_month,
    COUNT(*)                                                  AS calls,
    SUM(CASE WHEN call_result = '成約' THEN 1 ELSE 0 END)    AS contracts,
    AVG(CASE WHEN call_result = '成約' THEN 1.0 ELSE 0 END)  AS contract_rate
FROM calls
GROUP BY call_month
ORDER BY call_month;


-- ============================================================
-- 7. ハイパフォーマー定義（経験年数・成約率の相関確認）
-- ============================================================
SELECT
    a.experience_years,
    COUNT(DISTINCT a.agent_id)                                AS agent_count,
    AVG(CASE WHEN c.call_result = '成約' THEN 1.0 ELSE 0 END) AS avg_contract_rate
FROM calls c
JOIN agents a ON c.agent_id = a.agent_id
GROUP BY a.experience_years
ORDER BY a.experience_years;


-- ============================================================
-- 8. 成約率の高い顧客セグメントへのコール集中効果試算
--    （仮に上位セグメントへのコール比率を20%増やした場合）
-- ============================================================
WITH segment_stats AS (
    SELECT
        customer_age_group,
        customer_gender,
        COUNT(*)                                                  AS calls,
        AVG(CASE WHEN call_result = '成約' THEN 1.0 ELSE 0 END)  AS contract_rate
    FROM calls
    GROUP BY customer_age_group, customer_gender
),
overall AS (
    SELECT
        SUM(calls)                              AS total_calls,
        SUM(calls * contract_rate)              AS current_contracts
    FROM segment_stats
)
SELECT
    o.total_calls,
    ROUND(o.current_contracts)                  AS current_contracts,
    -- 上位25%セグメントへ20%コールを移した場合の試算
    ROUND(o.current_contracts * 1.05)           AS simulated_contracts,
    ROUND(o.current_contracts * 1.05) - ROUND(o.current_contracts) AS incremental_contracts
FROM overall o;


-- ============================================================
-- 9. チーム内 成約率ランキング（RANK / DENSE_RANK Window関数）
-- ============================================================
WITH agent_stats AS (
    SELECT
        a.agent_id,
        a.name,
        a.team,
        a.experience_years,
        COUNT(*)                                                   AS calls,
        SUM(CASE WHEN c.call_result = '成約' THEN 1 ELSE 0 END)   AS contracts,
        AVG(CASE WHEN c.call_result = '成約' THEN 1.0 ELSE 0 END) AS contract_rate
    FROM calls c
    JOIN agents a ON c.agent_id = a.agent_id
    GROUP BY a.agent_id, a.name, a.team, a.experience_years
)
SELECT
    agent_id,
    name,
    team,
    experience_years,
    calls,
    contracts,
    ROUND(contract_rate * 100, 2)                                     AS contract_rate_pct,
    RANK()       OVER (PARTITION BY team ORDER BY contract_rate DESC) AS rank_in_team,
    DENSE_RANK() OVER (ORDER BY contract_rate DESC)                   AS rank_overall,
    ROUND(AVG(contract_rate) OVER (PARTITION BY team) * 100, 2)       AS team_avg_contract_rate_pct,
    ROUND(
        (contract_rate - AVG(contract_rate) OVER (PARTITION BY team)) * 100, 2
    )                                                                  AS diff_from_team_avg_pct
FROM agent_stats
ORDER BY team, rank_in_team;


-- ============================================================
-- 10. 月次トレンド（前月比 / 移動平均 / 累計 Window関数）
-- ============================================================
WITH monthly_base AS (
    SELECT
        call_month,
        COUNT(*)                                                   AS calls,
        SUM(CASE WHEN call_result = '成約' THEN 1 ELSE 0 END)     AS contracts,
        AVG(CASE WHEN call_result = '成約' THEN 1.0 ELSE 0 END)   AS contract_rate
    FROM calls
    GROUP BY call_month
)
SELECT
    call_month,
    calls,
    contracts,
    ROUND(contract_rate * 100, 2)                                       AS contract_rate_pct,
    -- 前月比（件数・成約率）
    LAG(contracts, 1)   OVER (ORDER BY call_month)                      AS prev_month_contracts,
    contracts - LAG(contracts, 1) OVER (ORDER BY call_month)            AS mom_contract_diff,
    ROUND(
        (contract_rate - LAG(contract_rate, 1) OVER (ORDER BY call_month)) * 100, 2
    )                                                                    AS mom_rate_diff_pct,
    -- 3ヶ月移動平均成約率
    ROUND(
        AVG(contract_rate) OVER (
            ORDER BY call_month
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ) * 100, 2
    )                                                                    AS moving_avg_3m_pct,
    -- 累計成約数（YTD）
    SUM(contracts) OVER (ORDER BY call_month ROWS UNBOUNDED PRECEDING)  AS ytd_contracts
FROM monthly_base
ORDER BY call_month;


-- ============================================================
-- 11. 担当者別 コールごとの成約確率スコアリング
--     （セグメント成約率を個票に付与し、コール優先度を算出）
-- ============================================================
WITH segment_rate AS (
    SELECT
        customer_age_group,
        customer_gender,
        AVG(CASE WHEN call_result = '成約' THEN 1.0 ELSE 0 END) AS segment_contract_rate
    FROM calls
    GROUP BY customer_age_group, customer_gender
),
agent_rate AS (
    SELECT
        agent_id,
        AVG(CASE WHEN call_result = '成約' THEN 1.0 ELSE 0 END) AS agent_contract_rate
    FROM calls
    GROUP BY agent_id
),
hour_rate AS (
    SELECT
        call_hour,
        AVG(CASE WHEN call_result = '成約' THEN 1.0 ELSE 0 END) AS hour_contract_rate
    FROM calls
    GROUP BY call_hour
),
scored AS (
    SELECT
        c.call_id,
        c.call_datetime,
        c.agent_id,
        c.customer_age_group,
        c.customer_gender,
        c.call_result,
        -- 単純加重スコア: セグメント率・担当者率・時間帯率の平均
        ROUND(
            (s.segment_contract_rate + ar.agent_contract_rate + hr.hour_contract_rate) / 3.0 * 100,
            2
        )                                                            AS priority_score,
        NTILE(4) OVER (
            ORDER BY (s.segment_contract_rate + ar.agent_contract_rate + hr.hour_contract_rate) DESC
        )                                                            AS priority_quartile
    FROM calls c
    JOIN segment_rate s  ON c.customer_age_group = s.customer_age_group
                        AND c.customer_gender    = s.customer_gender
    JOIN agent_rate ar   ON c.agent_id = ar.agent_id
    JOIN hour_rate hr    ON c.call_hour = hr.call_hour
)
SELECT
    call_id,
    call_datetime,
    agent_id,
    customer_age_group,
    customer_gender,
    call_result,
    priority_score,
    CASE priority_quartile
        WHEN 1 THEN '🔴 最優先'
        WHEN 2 THEN '🟡 高優先'
        WHEN 3 THEN '🟢 中優先'
        ELSE       '⚪ 低優先'
    END AS priority_label
FROM scored
ORDER BY priority_score DESC
LIMIT 100;


-- ============================================================
-- 12. コール結果ファネル分析（CTE多段 + 割合計算）
-- ============================================================
WITH total AS (
    SELECT COUNT(*) AS all_calls FROM calls
),
funnel AS (
    SELECT
        CASE
            WHEN call_result = '不在'          THEN '1_不在'
            WHEN call_result = '断り'          THEN '2_接触_断り'
            WHEN call_result = 'コールバック希望' THEN '3_接触_CB希望'
            WHEN call_result = '検討中'        THEN '4_接触_検討中'
            WHEN call_result = '成約'          THEN '5_成約'
        END                                                       AS stage,
        COUNT(*)                                                  AS calls
    FROM calls
    GROUP BY call_result
),
funnel_with_rate AS (
    SELECT
        f.stage,
        f.calls,
        ROUND(f.calls * 100.0 / t.all_calls, 2)                  AS pct_of_total,
        SUM(f.calls) OVER (ORDER BY f.stage DESC)                 AS remaining_calls,
        ROUND(
            SUM(f.calls) OVER (ORDER BY f.stage DESC) * 100.0 / t.all_calls,
            2
        )                                                          AS pct_remaining
    FROM funnel f
    CROSS JOIN total t
)
SELECT
    stage,
    calls,
    pct_of_total,
    remaining_calls,
    pct_remaining
FROM funnel_with_rate
ORDER BY stage;


-- ============================================================
-- 13. BigQuery 向け: PERCENTILE_CONT / APPROX_QUANTILES
--     エージェント通話時間の分位数分析
-- ============================================================
-- BigQuery Standard SQL
SELECT
    a.team,
    a.name,
    COUNT(*)                                                              AS calls,
    ROUND(AVG(c.call_duration_min), 1)                                   AS avg_duration_min,
    -- 中央値（PERCENTILE_CONT はウィンドウ関数として使用）
    PERCENTILE_CONT(c.call_duration_min, 0.5)
        OVER (PARTITION BY a.team)                                        AS median_duration_by_team,
    -- 上位25%閾値（通話が長いほど成約率が高い仮説の検証に）
    PERCENTILE_CONT(c.call_duration_min, 0.75)
        OVER (PARTITION BY a.team)                                        AS p75_duration_by_team,
    AVG(CASE WHEN c.call_result = '成約' THEN 1.0 ELSE 0 END)            AS contract_rate
FROM calls c
JOIN agents a ON c.agent_id = a.agent_id
GROUP BY a.team, a.name
ORDER BY a.team, contract_rate DESC;
