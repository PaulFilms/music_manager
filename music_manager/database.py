'''
Managing audio files through local database

Include:
    - DB_NAME constant
    - DB_TAGS_KEYS constant
    - Folder class
    - File class
    - scan
    - sync
    - format_size


'''
from __future__ import annotations
import os, re
from typing import TYPE_CHECKING, Callable
from datetime import datetime
from dataclasses import dataclass, fields
from pathlib import Path

from mysqlite import SQL
from music_manager.tags import Extractor

# from .tags import SUPPORTED_EXTENSIONS
SUPPORTED_EXTENSIONS: set[str] = {
    ".mp3", ".mp4", ".m4a", ".m4b", ".m4p",
    ".flac", ".ogg", ".oga", ".opus",
    ".wav", ".aiff", ".aif", ".wv", ".ape",
    ".webm", 
}
DB_NAME = 'mmngr.db'
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
    , "genre"	    TEXT
    , "year"	    INTEGER
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

-- CREATE VIEW IF NOT EXISTS view_reps_tag_hash AS
-- SELECT tag_hash, COUNT(*) AS total
-- FROM files
-- GROUP BY tag_hash
-- HAVING COUNT(*) > 1;

-- CREATE INDEX idx_files_tag_hash
-- ON files(tag_hash);

-- CREATE INDEX idx_files_track_key
-- ON files(track_key);

CREATE INDEX idx_files_folder
ON files(path);
'''
DB_TAGS_KEYS = {
    'artist', 'title', 'album', 'genre', 'year', 'bpm', 'comment', 'duration', 'track_key'
}

def format_size(size) -> str:
    '''Format file size in human-readable form.'''
    if size > 1000000:
        return f"{size/1000000:.1f} MB"
    elif size > 1000:
        return f"{size/1000:.1f} kB"
    return f"{size} B"

@dataclass
class Folder:
    path:       str
    mtime:      int
    nfiles:      int

    def to_dict(self) -> dict:
        return {
            'path': self.path,
            'mtime': self.mtime,
            'nfiles': self.nfiles
        }

    # def insert(self, db: SQL):
    #     sql = ''' 
    #     INSERT INTO folders (
    #         path, mtime, nfiles
    #     )
    #     VALUES (?, ?, ?)
    #     '''
    #     db.execute(
    #         sql, 
    #         (
    #             self.path, 
    #             self.mtime,
    #             self.nfiles
    #         ),
    #         commit=True
    #     )
    
    # def update(self, db: SQL):
    #     db.update(
    #         'folders', 
    #         {'mtime': self.mtime, 'nfiles': self.nfiles},
    #         {'path': self.path}
    #     )

    # def delete(self, db: SQL, path: str):
    #     db.execute(
    #         'DELETE FROM folders WHERE path=?',
    #         [path],
    #         commit=True
    #     )

@dataclass
class File:
    filename:   str
    path:       str
    size:       int
    mtime:      int
    artist:     str = None
    title:      str = None
    album:      str = None
    genre:      str = None
    year:       int = None
    bpm:        float = None
    comment:    str = None
    duration:   float = None
    track_key:  int = None
    # tag_hash:   int = None

    def to_dict(self) -> dict:
        return {
            'filename': self.filename,
            'path': self.path,
            'size': self.size,
            'mtime': self.mtime,
            'artist': self.artist,
            'title': self.title,
            'album': self.album,
            'genre': self.genre,
            'year': self.year,
            'bpm': self.bpm,
            'comment': self.comment,
            'duration': self.duration,
            'track_key': self.track_key,
            # 'tag_hash': self.tag_hash
        }

    def get_tags(self, root: str | Path = ".") -> dict:
        tags = Extractor.get_tags(Path(root) / self.path / self.filename)
        if tags is None:
            tags = {}

        for key in DB_TAGS_KEYS:
            setattr(self, key, tags.get(key))

        return tags

    @classmethod
    def get_file(
        cls,
        audiofile_path: str | Path,
        root: str | Path | None = None,
    ) -> File:
        audiofile_path = Path(audiofile_path).resolve()
        root_path = Path(root).resolve() if root is not None else None
        stat = audiofile_path.stat()

        current = cls(
            filename=audiofile_path.name,
            path=(
                str(audiofile_path.parent.relative_to(root_path))
                if root_path is not None
                else str(audiofile_path.parent)
            ),
            size=stat.st_size,
            mtime=stat.st_mtime_ns,
        )
        current.get_tags(root_path if root_path is not None else ".")
        return current


    # def insert(self, db: SQL):

    #     cols = [f.name for f in fields(self)]
    #     values = [getattr(self, c) for c in cols]

    #     sql = f"""
    #         INSERT INTO files (
    #             {', '.join(cols)}
    #         )
    #         VALUES (
    #             {', '.join('?' for _ in cols)}
    #         )
    #     """

    #     db.execute(
    #         sql,
    #         values,
    #         commit=True
    #     )

    # def update(self, db: SQL):
    #     db.update(
    #         'files', 
    #         {
    #             f.name: getattr(self, f.name) 
    #             for f in fields(self)
    #         },
    #         {'filename': self.filename}
    #     )

    # def delete(self, db: SQL, filename: str):
    #     print(filename)
    #     db.execute(
    #         'DELETE FROM files WHERE filename=?',
    #         [filename],
    #         commit=True
    #     )


def scan(root: str | Path, current_path: str | Path) -> tuple[list[Folder], list[File]]:
    '''
    Scan the given root directory and return a list of Folder and Audio File objects.

    `Parameters`:
    - root: The root directory to scan.  

    `Returns`:
    - A tuple containing a list of Folder objects and a list of File objects.  
    '''
    root = Path(root)
    current_path = Path(current_path)

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
                    # if ext not in TinyTag.SUPPORTED_FILE_EXTENSIONS:
                    #     continue
                    if ext not in SUPPORTED_EXTENSIONS:
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

    _scan(current_path)            

    return folders, files


## Problemas sync
# El scan detecta los items de folders y files y si no los encuentra en la db, los elimina

# from time import sleep

# def sync(root: str | Path, folders: list[Folder], files: list[File], progress: Callable[[int, str], None] | None = None) -> str:
#     '''
#     Synchronize the database with the scanned folders and files.

#     `Parameters:`
#     - root: The root path of the music library.  
#     - folders: List of Folder objects obtained from scanning the filesystem.  
#     - files: List of File objects obtained from scanning the filesystem.  
    
#     `Returns:`
#     - A string containing the log of the synchronization process.  

#     `Optional:`
#     - progress: Optional callable to report progress.  
#     '''
#     def report(percent: float, message: str, log: str) -> None:
#         log += f"{message}  \n"
#         if progress is not None:
#             progress(percent, message)
#         return log

#     ## root path
#     root = Path(root)
#     path_db = root / DB_NAME
#     if not path_db.exists():
#         raise FileNotFoundError(f"Database not found at {path_db}")

#     ## database
#     db = SQL(path_db)
#     required_tables = ["folders", "files"]
#     existing_tables = [row[0] for row in db.select("SELECT name FROM sqlite_master WHERE type='table'")]
#     for table in required_tables:
#         if table not in existing_tables:
#             raise ValueError(f"Database is missing required table: {table}")
    
#     ## set of scanned and database items
#     folders_scan = { f.path: f for f in folders }
#     folders_db = { row[0]: row for row in db.select("SELECT path, mtime, nfiles FROM folders") }
#     files_scan = { f.filename: f for f in files }
#     files_db = { row[0]: row for row in db.select("SELECT * FROM files") }

#     paths_scan = set(folders_scan.keys())
#     paths_db = set(folders_db.keys())
#     filenames_scan = set(files_scan.keys())
#     filenames_db = set(files_db.keys())

#     folders_inserts = [ folders_scan[path] for path in paths_scan - paths_db ]
#     folders_delete = [ folders_scan[path] for path in paths_db - paths_scan ]
#     folders_update = [ folders_scan[path] for path in paths_scan & paths_db if not (
#         folders_scan[path].mtime == folders_db[path][1] and 
#         folders_scan[path].nfiles == folders_db[path][2]
#     ) ]
#     files_inserts = [ files_scan[filename] for filename in filenames_scan - filenames_db ]
#     files_deletes = [ files_scan[filename] for filename in filenames_db - filenames_scan ]
#     files_update = [ files_scan[filename] for filename in filenames_scan & filenames_db if not (
#         files_scan[filename].path == files_db[filename][1] and
#         files_scan[filename].size == files_db[filename][2] and
#         files_scan[filename].mtime == files_db[filename][3]
#     ) ]
#     total_items = len(folders_inserts) + len(folders_delete) + len(folders_update) + len(files_inserts) + len(files_deletes) + len(files_update)
    
#     ## SQL OPERATIONS
#     progress_inc = 0
#     log = ""

#     if total_items == 0:
#         log = report(100, "NO CHANGES DETECTED", log)
#         return log
    
#     log = report(progress_inc*100 / total_items, "STARTING DB OPERATIONS", log)

#     for folder in folders_inserts:
#         sql = '''INSERT INTO folders (path, mtime, nfiles) VALUES (?, ?, ?);'''
#         db.execute(sql, (folder.path, folder.mtime, folder.nfiles), commit=True)
#         log = report(progress_inc*100 / total_items, f"FOLDER ADDED: {folder.path}", log)
#         progress_inc += 1

#     for folder in folders_delete:
#         sql = '''DELETE FROM folders WHERE path = ?;'''
#         db.execute(sql, (folder[0],), commit=True)
#         log = report(progress_inc*100 / total_items, f"FOLDER DELETED: {folder[0]}", log)
#         progress_inc += 1

#     for folder in folders_update:
#         sql = '''UPDATE folders SET mtime = ?, nfiles = ? WHERE path = ?;'''
#         db.execute(sql, (folder.mtime, folder.nfiles, folder.path), commit=True)
#         log = report(progress_inc*100 / total_items, f"FOLDER UPDATED: {folder.path}", log)
#         progress_inc += 1

#     for file in files_inserts:
#         file.get_tags(root)
#         columns = []; values = []
#         for f in fields(file):
#             if getattr(file, f.name) is not None:
#                 columns.append(f.name)
#                 values.append(getattr(file, f.name))
#         sql = f'''INSERT INTO files ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)});'''
#         db.execute(sql, values, commit=True)
#         log = report(progress_inc*100 / total_items, f"FILE ADDED: {file.filename}", log)
#         progress_inc += 1

#     for file in files_deletes:
#         sql = '''DELETE FROM files WHERE filename = ? AND path = ?;'''
#         db.execute(sql, (file[0], file[1]), commit=True)
#         log = report(progress_inc*100 / total_items, f"FILE DELETED: {file[0]}", log)
#         progress_inc += 1

#     for file in files_update:
#         file.get_tags(root)
#         columns = []; values = []
#         for f in fields(file):
#             if getattr(file, f.name) is not None:
#                 columns.append(f.name)
#                 values.append(getattr(file, f.name))
#         sql = f"""
#         UPDATE files 
#         SET {', '.join(f"{col} = ?" for col in columns)}
#         WHERE filename = '{file.filename}' AND path = '{file.path}';
#         """
#         db.execute(sql, values, commit=True)
#         log = report(progress_inc*100 / total_items, f"FILE UPDATED: {file.filename}", log)
#         progress_inc += 1

#     log = report(100, "DB OPERATIONS COMPLETED", log)
    
#     return log


def sync(
    root: str | Path,
    folders: list[Folder],
    files: list[File],
    progress: Callable[[float, str], None] | None = None,
) -> str:
    """Synchronize a complete scan, logging individual failures."""

    def report(percent: float, message: str, log: str) -> str:
        log += f"{message}  \n"
        if progress is not None:
            progress(percent, message)
        return log

    root = Path(root)
    path_db = root / DB_NAME
    if not path_db.exists():
        raise FileNotFoundError(f"Database not found at {path_db}")

    db = SQL(path_db)
    existing_tables = {
        row[0]
        for row in db.select(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    for table in ("folders", "files"):
        if table not in existing_tables:
            raise ValueError(f"Database is missing required table: {table}")

    log = ""
    tolerance_ns = 1_000_000_000

    folders_scan = {folder.path: folder for folder in folders}
    folders_db = {
        row[0]: row
        for row in db.select("SELECT path, mtime, nfiles FROM folders")
    }

    # Group before building the unique-filename dictionary.
    files_by_name: dict[str, list[File]] = {}
    for file in files:
        files_by_name.setdefault(file.filename, []).append(file)

    duplicate_names = {
        name for name, matches in files_by_name.items()
        if len(matches) > 1
    }
    for name in sorted(duplicate_names):
        locations = " | ".join(
            str(root / file.path / file.filename)
            for file in files_by_name[name]
        )
        log = report(
            0,
            f"FILE ERROR [DUPLICATE]: {name!r} | {locations}",
            log,
        )

    files_scan = {
        name: matches[0]
        for name, matches in files_by_name.items()
        if name not in duplicate_names
    }
    files_db = {
        row[0]: row
        for row in db.select(
            "SELECT filename, path, size, mtime FROM files"
        )
    }

    paths_scan = set(folders_scan)
    paths_db = set(folders_db)
    filenames_scan = set(files_scan)
    filenames_db = set(files_db)

    folders_inserts = [
        folders_scan[path] for path in paths_scan - paths_db
    ]
    folders_delete = [
        folders_db[path] for path in paths_db - paths_scan
    ]
    folders_update = [
        folders_scan[path]
        for path in paths_scan & paths_db
        if (
            folders_db[path][1] is None
            or abs(
                folders_scan[path].mtime - folders_db[path][1]
            ) > tolerance_ns
            or folders_scan[path].nfiles != folders_db[path][2]
        )
    ]

    files_inserts = [
        files_scan[name] for name in filenames_scan - filenames_db
    ]
    # Duplicates are excluded from processing, not treated as missing.
    files_deletes = [
        files_db[name]
        for name in filenames_db - filenames_scan - duplicate_names
    ]
    files_update = [
        files_scan[name]
        for name in filenames_scan & filenames_db
        if (
            files_scan[name].path != files_db[name][1]
            or files_scan[name].size != files_db[name][2]
            or files_db[name][3] is None
            or abs(
                files_scan[name].mtime - files_db[name][3]
            ) > tolerance_ns
        )
    ]

    operations = [
        ("FOLDER", "INSERT", folders_inserts),
        ("FOLDER", "DELETE", folders_delete),
        ("FOLDER", "UPDATE", folders_update),
        ("FILE", "INSERT", files_inserts),
        ("FILE", "DELETE", files_deletes),
        ("FILE", "UPDATE", files_update),
    ]
    total_items = sum(len(items) for _, _, items in operations)
    processed = 0
    error_count = 0

    if total_items == 0:
        return report(
            100,
            f"NO DB OPERATIONS: {len(duplicate_names)} DUPLICATE NAMES",
            log,
        )

    log = report(0, "STARTING DB OPERATIONS", log)
    success_labels = {
        "INSERT": "ADDED",
        "DELETE": "DELETED",
        "UPDATE": "UPDATED",
    }

    for kind, operation, items in operations:
        for item in items:
            if kind == "FOLDER":
                item_path = item[0] if operation == "DELETE" else item.path
                display_path = str(root / item_path)
            else:
                filename = item[0] if operation == "DELETE" else item.filename
                item_path = item[1] if operation == "DELETE" else item.path
                display_path = str(root / item_path / filename)

            stage = "SQL"

            try:
                if kind == "FOLDER":
                    if operation == "INSERT":
                        sql = (
                            "INSERT INTO folders (path, mtime, nfiles) "
                            "VALUES (?, ?, ?)"
                        )
                        values = (item.path, item.mtime, item.nfiles)
                    elif operation == "DELETE":
                        sql = "DELETE FROM folders WHERE path = ?"
                        values = (item[0],)
                    else:
                        sql = (
                            "UPDATE folders SET mtime = ?, nfiles = ? "
                            "WHERE path = ?"
                        )
                        values = (item.mtime, item.nfiles, item.path)

                elif operation == "DELETE":
                    sql = (
                        "DELETE FROM files "
                        "WHERE filename = ? AND path = ?"
                    )
                    values = (item[0], item[1])

                else:
                    stage = "TAGS"
                    item.get_tags(root)

                    stage = "NORMALIZATION"
                    columns = []
                    values = []

                    for field in fields(item):
                        # filename is the current database primary key.
                        if operation == "UPDATE" and field.name == "filename":
                            continue

                        value = getattr(item, field.name)
                        # Preserve existing tags when extraction gives None.
                        if value is None:
                            continue

                        if isinstance(value, (list, tuple)):
                            value = ",".join(str(part) for part in value)

                        columns.append(field.name)
                        values.append(value)

                    if operation == "INSERT":
                        placeholders = ", ".join("?" for _ in columns)
                        sql = (
                            f"INSERT INTO files ({', '.join(columns)}) "
                            f"VALUES ({placeholders})"
                        )
                    else:
                        assignments = ", ".join(
                            f"{column} = ?" for column in columns
                        )
                        # Include the new path in SET, not in WHERE.
                        sql = (
                            f"UPDATE files SET {assignments} "
                            "WHERE filename = ?"
                        )
                        values.append(item.filename)

                    stage = "SQL"

                db.execute(sql, values, commit=True)

            except Exception as exc:
                error_count += 1
                message = (
                    f"{kind} ERROR [{operation}/{stage}]: {display_path} "
                    f"| {type(exc).__name__}: {exc}"
                )
            else:
                message = (
                    f"{kind} {success_labels[operation]}: {display_path}"
                )

            processed += 1
            log = report(processed * 100 / total_items, message, log)

    return report(
        100,
        f"DB OPERATIONS COMPLETED: "
        f"{total_items - error_count} SUCCESS, "
        f"{error_count} ERRORS, "
        f"{len(duplicate_names)} DUPLICATE NAMES EXCLUDED",
        log,
    )