CREATE TABLE IF NOT EXISTS calculation_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  expression TEXT NOT NULL,
  angle_mode TEXT NOT NULL DEFAULT 'deg',
  result TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_history_created ON calculation_history(created_at);
CREATE TABLE IF NOT EXISTS formulas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  expression TEXT NOT NULL,
  parameter_labels TEXT NOT NULL,
  angle_mode TEXT NOT NULL DEFAULT 'deg',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
