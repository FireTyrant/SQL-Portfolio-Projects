-- Extra exploration queries (run with: sqlite3 output/mega_millions.db < sql/explore.sql)
.headers on
.mode column

-- 1. Draws per era
SELECT e.label, COUNT(*) AS draws, MIN(d.draw_date) AS first_draw, MAX(d.draw_date) AS last_draw
FROM draws d JOIN eras e ON d.draw_date BETWEEN e.start_date AND e.end_date
GROUP BY e.era_id ORDER BY e.era_id;

-- 2. Top 10 white balls by raw count (all time)
SELECT number, COUNT(*) AS times_drawn
FROM draw_numbers WHERE ball_type = 'white'
GROUP BY number ORDER BY times_drawn DESC, number LIMIT 10;

-- 3. Most common white-ball pairs
SELECT a.number AS ball_a, b.number AS ball_b, COUNT(*) AS together
FROM draw_numbers a
JOIN draw_numbers b ON a.draw_date = b.draw_date
                   AND a.ball_type = 'white' AND b.ball_type = 'white'
                   AND a.number < b.number
GROUP BY a.number, b.number ORDER BY together DESC LIMIT 10;

-- 4. How many of the 5 white balls were odd, across all draws
WITH per_draw AS (
    SELECT draw_date, SUM(number % 2) AS odd_count
    FROM draw_numbers WHERE ball_type = 'white'
    GROUP BY draw_date
)
SELECT odd_count, COUNT(*) AS draws,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM per_draw GROUP BY odd_count ORDER BY odd_count;

-- 5. Distribution of the sum of the five white balls (current 5/70 matrix)
SELECT (n1 + n2 + n3 + n4 + n5) / 25 * 25 AS sum_bucket, COUNT(*) AS draws
FROM draws WHERE draw_date >= '2017-10-28'
GROUP BY sum_bucket ORDER BY sum_bucket;
