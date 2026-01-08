-- PRAGMA foreign_keys = ON;
-- PRAGMA journal_mode = WAL;
-- PRAGMA synchronous = NORMAL;

-- CREATE TABLE IF NOT EXISTS meta (
--     key TEXT PRIMARY KEY,
--     value TEXT
-- );

-- DROP TABLE IF EXISTS "files";
CREATE TABLE IF NOT EXISTS "files" (
	"path"	TEXT NOT NULL UNIQUE,
	"filename"	TEXT NOT NULL,
	"artist"	TEXT,
	"title"	TEXT,
	"album"	TEXT,
	"bpm"	NUMERIC,
	"comment"	TEXT,
	"duration"	REAL,
	"size"	INTEGER,
	"mtime"	INTEGER,
	"tag_hash"	TEXT,
	"firm"	TEXT,
	PRIMARY KEY("path")
);

-- DROP TABLE IF EXISTS "folders";
CREATE TABLE IF NOT EXISTS "folders" (
	"path"	TEXT NOT NULL UNIQUE,
	"filename"	TEXT,
	"mtime"	INTEGER,
	"files"	INTEGER,
	"firm"	TEXT,
	PRIMARY KEY("path")
);

CREATE VIEW IF NOT EXISTS view_reps_filename AS
SELECT filename, COUNT(*) AS total
FROM files
GROUP BY filename
HAVING COUNT(*) > 1;

CREATE VIEW IF NOT EXISTS view_reps_tag_hash AS
SELECT tag_hash, COUNT(*) AS total
FROM files
GROUP BY tag_hash
HAVING COUNT(*) > 1;

CREATE INDEX IF NOT EXISTS idx_files_mtime ON files(mtime);
-- CREATE INDEX IF NOT EXISTS idx_files_folder ON files(folder_path);