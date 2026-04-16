from django.db import connection

def create_tables():
    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER,
                youtube_video_id TEXT,
                title TEXT NOT NULL,
                description TEXT,
                thumbnail TEXT,
                FOREIGN KEY(course_id) REFERENCES courses(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                searched_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL,
                username TEXT,
                review_text TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL,
                watched INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS liked_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL UNIQUE,
                title TEXT,
                thumbnail TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watch_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL,
                title TEXT,
                watched_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)