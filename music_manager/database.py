'''
Managing audio files through local database

Include:
    - **
'''
import re
from datetime import datetime

SKIP_DIRS = {
    ".Spotlight-V100",
    ".Trashes",
    ".fseventsd",
    ".DocumentRevisions-V100",
    ".TemporaryItems",
    ".DS_Store",
    "__MACOSX",
}
INVALID_PATH_CHARS = r'<>:"/\\|?*\x00\x1F'
INVALID_RE = re.compile(f"[{re.escape(INVALID_PATH_CHARS)}]")

SQL_SCHEMA = '''
-- DROP TABLE IF EXISTS "meta";
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- DROP TABLE IF EXISTS "files";
CREATE TABLE IF NOT EXISTS "files" (
    id              INTEGER PRIMARY KEY,
	, "folder_id"	TEXT NOT NULL
	, "filename"	TEXT NOT NULL
	, "artist"	    TEXT
	, "title"	    TEXT
	, "album"	    TEXT
	, "bpm"	        NUMERIC
	, "comment"	    TEXT
	, "duration"	REAL
	, "size"	    INTEGER
	, "mtime"	    INTEGER
	, "track_key"	TEXT
    , "tag_hash"	TEXT
	, "firm"	    TEXT
    FOREIGN KEY(folder_id) REFERENCES folders(id)
);

-- DROP TABLE IF EXISTS "folders";
CREATE TABLE IF NOT EXISTS "folders" (
    id              INTEGER PRIMARY KEY
	, "name"	    TEXT
    , "parent_id"   INT
	, "mtime"	    INTEGER
	, "files"	    INTEGER
    , FOREIGN KEY(parent_id) REFERENCES folders(id)
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

CREATE INDEX idx_files_tag_hash
ON files(tag_hash);

CREATE INDEX idx_files_track_key
ON files(track_key);

CREATE INDEX idx_files_folder
ON files(folder_id);
'''

