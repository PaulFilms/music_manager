'''
Managing audio files through local database

Include:
    - **
'''
from __future__ import annotations
import os, re
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from mysqlite import *
from tinytag import TinyTag

SKIP_DIRS = {
    ".Spotlight-V100",
    ".Trashes",
    ".fseventsd",
    ".DocumentRevisions-V100",
    ".TemporaryItems",
    ".DS_Store",
    "__MACOSX",
}

SKIP_PREFIXES = (
    ".", 
    "temp.db",
    "__MACOSX",
)

SQL_SCHEMA = '''
-- DROP TABLE IF EXISTS "meta";
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- DROP TABLE IF EXISTS "files";
CREATE TABLE IF NOT EXISTS "files" (
    id              INTEGER PRIMARY KEY
--	, "folder_id"	TEXT NOT NULL
	, "path"	    TEXT NOT NULL
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
--    , FOREIGN KEY(folder_id) REFERENCES folders(id)
--    , FOREIGN KEY(path) REFERENCES folders(path)
);

-- DROP TABLE IF EXISTS "folders";
CREATE TABLE IF NOT EXISTS "folders" (
    id              INTEGER PRIMARY KEY
	, "path"	    TEXT
--    , "parent_id"   INTEGER
	, "mtime"	    INTEGER
	, "files"	    INTEGER
--    , FOREIGN KEY(parent_id) REFERENCES folders(id)
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

-- CREATE INDEX idx_files_tag_hash
-- ON files(tag_hash);

-- CREATE INDEX idx_files_track_key
-- ON files(track_key);

CREATE INDEX idx_files_folder
ON files(path);
'''

@dataclass
class Folder:
    # id:         int      
    # name:       str
    path:       str
    # parent_id:  int
    mtime:      int
    files:      int

    @classmethod
    def scan(cls, root: Path, path: str | Path) -> Folder:
        p = Path(path)
        stat = p.stat()
        # mtime = int(stat.st_mtime * 1e6)
        # mtime = stat.st_mtime_ns
        # files = sum(1 for _ in os.scandir(path) if _.is_file())
        # files = sum(1 for _ in p.iterdir())
        return cls(
            id = None, # Hay que buscar en la db el id, si es nuevo None
            # name = p.name,
            path = str(p.relative_to(root)),
            # parent_id = p.parent.name, # Hay que buscar en la db el id
            mtime = stat.st_mtime_ns,
            files = None,
        )

    def insert(self, db: SQL):
        print("Folder.insert")
        # sql = ''' 
        # INSERT INTO folders (
        #     path, mtime, files, firm
        # )
        # VALUES (?, ?, ?, ?)
        # '''
        # db.execute(
        #     sql, 
        #     (path, mtime, files, get_firm()),
        #     commit=True
        # )
        pass

@dataclass
class File:
    id:         int
    path:       int
    filename:   int
    artist:     int = None
    title:      int = None
    album:      int = None
    bpm:        int = None
    comment:    int = None
    duration:   int = None
    size:       int = None
    mtime:      int = None
    track_key:  int = None
    tag_hash:   int = None

    @classmethod
    def scan(cls, root: Path, path: str):
        p = Path(path)
        stat = p.stat()
        # mtime = int(stat.st_mtime * 1e6)
        # mtime = stat.st_mtime_ns
        return cls(
            id = None,
            path = str(p.parent.relative_to(root)),
            filename = p.name,
            mtime = stat.st_mtime_ns
        )

def scan(root: str | Path) -> None:
    root = Path(root)

    folders: list[Folder] = []
    files: list[File] = []

    def _scan(path: Path):
        with os.scandir(path) as entries:

            for entry in entries:

                if entry.name.startswith(SKIP_PREFIXES):
                    continue

                if entry.is_dir(follow_symlinks=False):
                    folders.append(
                        Folder.scan(root, entry.path)
                    )
                    _scan(Path(entry.path))

                elif entry.is_file(follow_symlinks=False):
                    ext = Path(entry.name).suffix.lower()
                    if ext not in TinyTag.SUPPORTED_FILE_EXTENSIONS:
                        continue
                    files.append(
                        File.scan(root, entry.path)
                    )

    _scan(root)            
    
    # for e in folders: print(e)
    # for e in files: print(e)

    return folders, files