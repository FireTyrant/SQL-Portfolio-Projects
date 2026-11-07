-- Mega Millions schema (SQLite)
DROP TABLE IF EXISTS draw_numbers;
DROP TABLE IF EXISTS draws;
DROP TABLE IF EXISTS eras;

-- The game's number matrix has changed over time. Every draw is tagged with
-- the era it belongs to so numbers are only compared against draws in which
-- they could actually have been drawn.
CREATE TABLE eras (
    era_id     INTEGER PRIMARY KEY,
    start_date TEXT NOT NULL,      -- ISO yyyy-mm-dd, inclusive
    end_date   TEXT NOT NULL,      -- inclusive
    white_max  INTEGER NOT NULL,   -- white balls are 1..white_max (5 drawn)
    mega_max   INTEGER NOT NULL,   -- Mega Ball is 1..mega_max (1 drawn)
    label      TEXT NOT NULL
);

INSERT INTO eras VALUES
    (1, '2002-05-17', '2005-06-21', 52, 52, '5/52 + 1/52'),
    (2, '2005-06-22', '2013-10-18', 56, 46, '5/56 + 1/46'),
    (3, '2013-10-19', '2017-10-27', 75, 15, '5/75 + 1/15'),
    (4, '2017-10-28', '2025-04-07', 70, 25, '5/70 + 1/25'),
    (5, '2025-04-08', '9999-12-31', 70, 24, '5/70 + 1/24 ($5 game)');

CREATE TABLE draws (
    draw_date  TEXT PRIMARY KEY,   -- ISO yyyy-mm-dd
    n1 INTEGER NOT NULL, n2 INTEGER NOT NULL, n3 INTEGER NOT NULL,
    n4 INTEGER NOT NULL, n5 INTEGER NOT NULL,
    mega_ball  INTEGER NOT NULL,
    multiplier INTEGER,            -- NULL when not offered / not reported
    source     TEXT NOT NULL       -- 'megamillions_com' (official) or 'ny_2002_2010'
);

-- Long (normalized) form: one row per ball drawn. Makes counting easy.
CREATE TABLE draw_numbers (
    draw_date TEXT NOT NULL REFERENCES draws(draw_date),
    ball_type TEXT NOT NULL CHECK (ball_type IN ('white', 'mega')),
    number    INTEGER NOT NULL,
    PRIMARY KEY (draw_date, ball_type, number)
);

CREATE INDEX idx_draw_numbers_lookup ON draw_numbers (ball_type, number, draw_date);
