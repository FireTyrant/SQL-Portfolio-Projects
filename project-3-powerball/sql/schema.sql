-- Powerball schema (SQLite)
DROP TABLE IF EXISTS draw_numbers;
DROP TABLE IF EXISTS draws;
DROP TABLE IF EXISTS eras;

-- Powerball's number matrix has changed 6 times since 1992. Every draw is
-- tagged with its era so numbers are only compared against draws in which
-- they could actually have been drawn.
CREATE TABLE eras (
    era_id     INTEGER PRIMARY KEY,
    start_date TEXT NOT NULL,      -- ISO yyyy-mm-dd, inclusive
    end_date   TEXT NOT NULL,      -- inclusive
    white_max  INTEGER NOT NULL,   -- white balls are 1..white_max (5 drawn)
    power_max  INTEGER NOT NULL,   -- Powerball is 1..power_max (1 drawn)
    label      TEXT NOT NULL
);

INSERT INTO eras VALUES
    (1, '1992-04-22', '1997-11-04', 45, 45, '5/45 + 1/45'),
    (2, '1997-11-05', '2002-10-08', 49, 42, '5/49 + 1/42'),
    (3, '2002-10-09', '2005-08-30', 53, 42, '5/53 + 1/42'),
    (4, '2005-08-31', '2009-01-06', 55, 42, '5/55 + 1/42'),
    (5, '2009-01-07', '2012-01-17', 59, 39, '5/59 + 1/39'),
    (6, '2012-01-18', '2015-10-06', 59, 35, '5/59 + 1/35'),
    (7, '2015-10-07', '9999-12-31', 69, 26, '5/69 + 1/26');

CREATE TABLE draws (
    draw_date  TEXT PRIMARY KEY,   -- ISO yyyy-mm-dd
    n1 INTEGER NOT NULL, n2 INTEGER NOT NULL, n3 INTEGER NOT NULL,
    n4 INTEGER NOT NULL, n5 INTEGER NOT NULL,
    powerball  INTEGER NOT NULL,
    power_play INTEGER,            -- NULL before 2010 / when not reported
    source     TEXT NOT NULL       -- 'ny_open_data' or 'archive_1992_2010'
);

-- Long (normalized) form: one row per ball drawn. Makes counting easy.
CREATE TABLE draw_numbers (
    draw_date TEXT NOT NULL REFERENCES draws(draw_date),
    ball_type TEXT NOT NULL CHECK (ball_type IN ('white', 'power')),
    number    INTEGER NOT NULL,
    PRIMARY KEY (draw_date, ball_type, number)
);

CREATE INDEX idx_draw_numbers_lookup ON draw_numbers (ball_type, number, draw_date);
