-- Per-number statistics for one ball type (:ball_type = 'white' or 'mega').
--
-- For every number that can be drawn in the CURRENT game, compare how often it
-- actually hit against how often pure chance says it should have hit, using
-- only draws where that number was eligible (e.g. white 71-75 only existed
-- 2013-2017, Mega Ball 25 stopped existing in April 2025).
--
--   expected_*  = sum over eligible draws of (balls drawn / balls in drum)
--   lift        = hits / expected   (1.00 = exactly average)
WITH ordered AS (
    SELECT d.draw_date,
           ROW_NUMBER() OVER (ORDER BY d.draw_date DESC) AS draws_ago,
           CASE WHEN :ball_type = 'white' THEN e.white_max ELSE e.mega_max END AS ball_max,
           CASE WHEN :ball_type = 'white' THEN 5.0 ELSE 1.0 END                AS picks
    FROM draws d
    JOIN eras e ON d.draw_date BETWEEN e.start_date AND e.end_date
),
current_max AS (
    SELECT ball_max FROM ordered WHERE draws_ago = 1
),
numbers(n) AS (
    SELECT 1
    UNION ALL
    SELECT n + 1 FROM numbers WHERE n < (SELECT ball_max FROM current_max)
),
eligible AS (
    SELECT nb.n, o.draw_date, o.draws_ago, o.picks / o.ball_max AS p
    FROM numbers nb
    JOIN ordered o ON nb.n <= o.ball_max
),
hits AS (
    SELECT number AS n, draw_date FROM draw_numbers WHERE ball_type = :ball_type
)
SELECT e.n                                                                   AS number,
       COUNT(h.n)                                                            AS hits_all,
       SUM(e.p)                                                              AS expected_all,
       SUM(CASE WHEN e.draws_ago <= :recent_draws AND h.n IS NOT NULL THEN 1 ELSE 0 END) AS hits_recent,
       SUM(CASE WHEN e.draws_ago <= :recent_draws THEN e.p ELSE 0 END)       AS expected_recent,
       COALESCE(MIN(CASE WHEN h.n IS NOT NULL THEN e.draws_ago END) - 1,
                COUNT(*))                                                    AS draws_since_last,
       MAX(CASE WHEN h.n IS NOT NULL THEN e.draw_date END)                   AS last_drawn,
       (SELECT p FROM eligible x WHERE x.n = e.n AND x.draws_ago = 1)        AS p_current
FROM eligible e
LEFT JOIN hits h ON h.n = e.n AND h.draw_date = e.draw_date
GROUP BY e.n
ORDER BY e.n;
