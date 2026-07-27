'''
Managing audio files through local database

Include:
    - **
'''
from __future__ import annotations
import os, re
from datetime import datetime
from dataclasses import dataclass, fields
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
	"filename"	    TEXT PRIMARY KEY
    , "path"	    TEXT NOT NULL
	, "size"	    INTEGER
	, "mtime"	    INTEGER
	, "artist"	    TEXT
	, "title"	    TEXT
	, "album"	    TEXT
	, "bpm"	        NUMERIC
	, "comment"	    TEXT
	, "duration"	REAL
	, "track_key"	TEXT
);

-- DROP TABLE IF EXISTS "folders";
CREATE TABLE IF NOT EXISTS "folders" (
    "path"	        TEXT
	, "mtime"	    INTEGER
	, "nfiles"	    INTEGER
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
    path:       str
    mtime:      int
    nfiles:      int

    def insert(self, db: SQL):
        sql = ''' 
        INSERT INTO folders (
            path, mtime, nfiles
        )
        VALUES (?, ?, ?)
        '''
        db.execute(
            sql, 
            (
                self.path, 
                self.mtime,
                self.nfiles
            ),
            commit=True
        )
    
    def update(self, db: SQL):
        db.update(
            'folders', 
            {'mtime': self.mtime, 'nfiles': self.nfiles},
            {'path': self.path}
        )

    @staticmethod
    def delete(db: SQL, path: str):
        db.execute(
            'DELETE FROM folders WHERE path=?',
            [path],
            commit=True
        )

@dataclass
class File:
    filename:   int
    path:       int
    size:       int
    mtime:      int
    artist:     int = None
    title:      int = None
    album:      int = None
    bpm:        int = None
    comment:    int = None
    duration:   int = None
    track_key:  int = None
    # tag_hash:   int = None

    def insert(self, db: SQL):

        cols = [f.name for f in fields(self)]
        values = [getattr(self, c) for c in cols]

        sql = f"""
            INSERT INTO files (
                {', '.join(cols)}
            )
            VALUES (
                {', '.join('?' for _ in cols)}
            )
        """

        db.execute(
            sql,
            values,
            commit=True
        )

    def update(self, db: SQL):
        db.update(
            'files', 
            {
                f.name: getattr(self, f.name) 
                for f in fields(self)
            },
            {'filename': self.filename}
        )

    @staticmethod
    def delete(db: SQL, filename: str):
        print(filename)
        db.execute(
            'DELETE FROM files WHERE filename=?',
            [filename],
            commit=True
        )

def scan(root: str | Path) -> tuple[list[Folder], list[File]]:
    root = Path(root)

    folders: list[Folder] = []
    files: list[File] = []

    def _scan(path: Path):

        nfiles: int = 0

        with os.scandir(path) as entries:

            for entry in entries:

                if entry.name.startswith(SKIP_PREFIXES):
                    continue

                if entry.is_dir(follow_symlinks=False):
                    _scan(Path(entry.path))

                elif entry.is_file(follow_symlinks=False):
                    ext = Path(entry.name).suffix.lower()
                    if ext not in TinyTag.SUPPORTED_FILE_EXTENSIONS:
                        continue

                    nfiles += 1
                    stat = entry.stat()
                    files.append(
                        File(
                            filename = entry.name,
                            path = str(path.relative_to(root)),
                            size = stat.st_size,
                            mtime = stat.st_mtime_ns
                        )
                    )

        # Ya conocemos el número de ficheros de ESTE directorio
        if path != root:
            stat = path.stat()

            folders.append(
                Folder(
                    path=str(path.relative_to(root)),
                    mtime=stat.st_mtime_ns,
                    nfiles=nfiles,
                )
            )

    _scan(root)            

    return folders, files

def sync(db: SQL, folders: list[Folder], files: list[File]):

    ## FOLDERS

    folders_scan = {
        f.path: f
        for f in folders
    }

    folders_db = {
        row[0]: row
        for row in db.select(
            "SELECT path, mtime, nfiles FROM folders"
        )
    }

    paths_scan = set(folders_scan.keys())
    paths_db = set(folders_db.keys())

    for path in paths_scan - paths_db:
        folder = folders_scan[path]
        folder.insert(db)
        print("INSERT FOLDER", path)

    for path in paths_scan & paths_db:
        folder = folders_scan[path]
        mtime_db = folders_db[path][1]
        files_db = folders_db[path][2]

        if not (
            folder.mtime == mtime_db and 
            folder.nfiles == files_db
        ):
            folder.update(db)
            print("UPDATE FOLDER", path)

    for path in paths_db - paths_scan:
        folder.delete(db, path)
        print("DELETE FOLDER", path)


    ## FILES

    files_scan = {
        f.filename: f
        for f in files
    }

    files_db = {
        row[0]: row
        for row in db.select(
            "SELECT * FROM files"
        )
    }

    filenames_scan = set(files_scan.keys())
    filenames_db = set(files_db.keys())

    for filename in filenames_scan - filenames_db:
        file = files_scan[filename]
        file.insert(db)
        print("INSERT FILE", filename)

    for filename in filenames_scan & filenames_db:
        file = files_scan[filename]
        path_db = files_db[filename][1]
        size_db = files_db[filename][2]
        mtime_db = files_db[filename][3]
        if not (
            file.path == path_db and
            file.size == size_db and
            file.mtime == mtime_db
        ):
            file.update(db)
            print("UPDATE FILE", filename)

    for filename in filenames_db - filenames_scan:
        file.delete(db, filename)
        print("DELETE FILE", filename)
