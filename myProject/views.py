import random

from .youtube_api import search_youtube_playlists, get_playlist_videos
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.db import connection
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

User = get_user_model()


# ---------------------------
# Helpers
# ---------------------------

def ensure_project_tables() -> None:
    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS creators (
                creator_id INTEGER PRIMARY KEY AUTOINCREMENT,
                youtube_channel_id VARCHAR(100) UNIQUE NOT NULL,
                creator_name VARCHAR(150) NOT NULL,
                channel_name VARCHAR(150),
                profile_image VARCHAR(255),
                description TEXT,
                subscriber_count BIGINT DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS playlists (
                playlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER NOT NULL,
                youtube_playlist_id VARCHAR(100) UNIQUE NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                thumbnail_url VARCHAR(255),
                language VARCHAR(50),
                level VARCHAR(50),
                video_count INTEGER DEFAULT 0,
                total_duration_seconds INTEGER DEFAULT 0,
                total_views BIGINT DEFAULT 0,
                completion_score DECIMAL(5,2) DEFAULT 0.00,
                is_complete_candidate BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                video_id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER NOT NULL,
                creator_id INTEGER NOT NULL,
                youtube_video_id VARCHAR(100) UNIQUE NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                embed_url VARCHAR(255) NOT NULL,
                thumbnail_url VARCHAR(255),
                duration_seconds INTEGER DEFAULT 0,
                views_count BIGINT DEFAULT 0,
                likes_count BIGINT DEFAULT 0,
                playlist_order INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS video_progress (
                progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                video_id INTEGER NOT NULL,
                watched_seconds INTEGER DEFAULT 0,
                progress_percent DECIMAL(5,2) DEFAULT 0.00,
                is_completed BOOLEAN DEFAULT 0,
                last_watched_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watch_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                video_id INTEGER NOT NULL,
                watched_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS liked_videos (
                like_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                video_id INTEGER NOT NULL,
                liked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, video_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                video_id INTEGER NOT NULL,
                rating TINYINT NULL,
                comment TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                history_paused BOOLEAN DEFAULT 0
            )
        """)


def get_or_create_default_creator_and_playlist():
    ensure_project_tables()

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT creator_id
            FROM creators
            WHERE youtube_channel_id = %s
        """, ["LOCAL_CHANNEL"])
        row = cursor.fetchone()

        if row:
            creator_id = row[0]
        else:
            cursor.execute("""
                INSERT INTO creators (
                    youtube_channel_id,
                    creator_name,
                    channel_name,
                    description,
                    subscriber_count
                ) VALUES (%s, %s, %s, %s, %s)
            """, [
                "LOCAL_CHANNEL",
                "EduTube+ Search",
                "EduTube+ Search",
                "Imported search results",
                0
            ])
            creator_id = cursor.lastrowid

        cursor.execute("""
            SELECT playlist_id
            FROM playlists
            WHERE youtube_playlist_id = %s
        """, ["LOCAL_PLAYLIST"])
        row = cursor.fetchone()

        if row:
            playlist_id = row[0]
        else:
            cursor.execute("""
                INSERT INTO playlists (
                    creator_id,
                    youtube_playlist_id,
                    title,
                    description,
                    thumbnail_url,
                    language,
                    level,
                    video_count,
                    total_duration_seconds,
                    total_views,
                    completion_score,
                    is_complete_candidate
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, [
                creator_id,
                "LOCAL_PLAYLIST",
                "Search Results",
                "Videos imported from YouTube search",
                "",
                "English",
                "All",
                0,
                0,
                0,
                0.00,
                0
            ])
            playlist_id = cursor.lastrowid

    return creator_id, playlist_id


def upsert_video_from_search(video: dict):
    creator_id, playlist_id = get_or_create_default_creator_and_playlist()

    youtube_video_id = video.get("video_id") or ""
    title = video.get("title") or "Untitled Video"
    description = video.get("description") or ""
    thumbnail = video.get("thumbnail") or ""
    views = int(video.get("views", 0))

    embed_url = f"https://www.youtube.com/embed/{youtube_video_id}"

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT video_id
            FROM videos
            WHERE youtube_video_id = %s
        """, [youtube_video_id])
        row = cursor.fetchone()

        if row:
            db_video_id = row[0]
            cursor.execute("""
                UPDATE videos
                SET title = %s,
                    description = %s,
                    thumbnail_url = %s,
                    embed_url = %s,
                    views_count = %s
                WHERE video_id = %s
            """, [title, description, thumbnail, embed_url, views, db_video_id])
            return db_video_id

        cursor.execute("""
            SELECT COALESCE(MAX(playlist_order), 0) + 1
            FROM videos
            WHERE playlist_id = %s
        """, [playlist_id])
        next_order = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO videos (
                playlist_id,
                creator_id,
                youtube_video_id,
                title,
                description,
                embed_url,
                thumbnail_url,
                duration_seconds,
                views_count,
                likes_count,
                playlist_order
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, [
            playlist_id,
            creator_id,
            youtube_video_id,
            title,
            description,
            embed_url,
            thumbnail,
            0,
            views,
            0,
            next_order
        ])

        return cursor.lastrowid
    
def get_db_video_by_youtube_id(youtube_video_id: str):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT video_id, playlist_id, creator_id, youtube_video_id, title, description,
                   embed_url, thumbnail_url, duration_seconds, views_count, likes_count,
                   playlist_order, created_at
            FROM videos
            WHERE youtube_video_id = %s
        """, [youtube_video_id])
        row = cursor.fetchone()

    if not row:
        return None

    return {
        "video_id": row[0],
        "playlist_id": row[1],
        "creator_id": row[2],
        "youtube_video_id": row[3],
        "title": row[4],
        "description": row[5],
        "embed_url": row[6],
        "thumbnail_url": row[7],
        "duration_seconds": row[8],
        "views_count": row[9],
        "likes_count": row[10],
        "playlist_order": row[11],
        "created_at": row[12],
    }


def get_db_video_by_internal_id(video_id: int):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT video_id, playlist_id, creator_id, youtube_video_id, title, description,
                   embed_url, thumbnail_url, duration_seconds, views_count, likes_count,
                   playlist_order, created_at
            FROM videos
            WHERE video_id = %s
        """, [video_id])
        row = cursor.fetchone()

    if not row:
        return None

    return {
        "video_id": row[0],
        "playlist_id": row[1],
        "creator_id": row[2],
        "youtube_video_id": row[3],
        "title": row[4],
        "description": row[5],
        "embed_url": row[6],
        "thumbnail_url": row[7],
        "duration_seconds": row[8],
        "views_count": row[9],
        "likes_count": row[10],
        "playlist_order": row[11],
        "created_at": row[12],
    }


# ---------------------------
# Auth pages
# ---------------------------

def login_page(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""

        if not email or not password:
            messages.error(request, "Please enter your email and password.")
            return redirect("login")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "Invalid email or password.")
            return redirect("login")
        except Exception:
            messages.error(request, "Something went wrong. Please try again.")
            return redirect("login")

        try:
            authed = authenticate(request, username=user.username, password=password)
        except Exception:
            messages.error(request, "Something went wrong. Please try again.")
            return redirect("login")

        if authed is None:
            messages.error(request, "Invalid email or password.")
            return redirect("login")

        login(request, authed)
        messages.success(request, "Signed in successfully.")
        return redirect("search")

    return render(request, "login.html")


def register_page(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""
        password2 = request.POST.get("password2") or ""

        if not name or not email or not password:
            messages.error(request, "Please fill in all required fields.")
            return redirect("register")

        if password2 and password != password2:
            messages.error(request, "Passwords do not match.")
            return redirect("register")

        try:
            if User.objects.filter(email=email).exists():
                messages.error(request, "An account with this email already exists.")
                return redirect("register")

            user = User.objects.create_user(username=email, email=email, password=password)
            user.first_name = name
            user.save(update_fields=["first_name"])
        except Exception:
            messages.error(request, "Something went wrong. Please try again.")
            return redirect("register")

        messages.success(request, "Account created. Please sign in.")
        return redirect("login")

    return render(request, "register.html")


def logout_stub(request: HttpRequest) -> HttpResponse:
    logout(request)
    messages.info(request, "You have been signed out.")
    return redirect("login")


# ---------------------------
# Search / Playlist / Video
# ---------------------------

def search_page(request: HttpRequest) -> HttpResponse:
    ensure_project_tables()

    query = (request.GET.get("q") or "").strip()
    language = (request.GET.get("language") or "").strip()
    category = (request.GET.get("category") or "").strip()

    playlists = []
    is_trending = False

    language_map = {
        "English": "en", "Hindi": "hi", "Spanish": "es",
        "French": "fr", "German": "de", "Portuguese": "pt",
        "Russian": "ru", "Japanese": "ja", "Korean": "ko",
        "Chinese": "zh", "Arabic": "ar", "Italian": "it",
        "Turkish": "tr", "Dutch": "nl", "Polish": "pl",
        "Vietnamese": "vi", "Thai": "th", "Indonesian": "id",
        "Malay": "ms", "Tamil": "ta", "Telugu": "te",
        "Bengali": "bn", "Urdu": "ur", "Marathi": "mr",
        "Gujarati": "gu", "Kannada": "kn", "Malayalam": "ml",
        "Punjabi": "pa", "Swedish": "sv", "Norwegian": "no",
        "Danish": "da", "Finnish": "fi", "Czech": "cs",
        "Romanian": "ro", "Hungarian": "hu", "Greek": "el",
        "Hebrew": "he", "Ukrainian": "uk", "Persian": "fa",
        "Swahili": "sw",
    }

    form_submitted = "q" in request.GET

    if query or category or language:
        if language and language not in language_map:
            messages.info(request, "Unknown language selected. Showing unfiltered results.")

        try:
            lang_code = language_map.get(language, "")
            search_query = query
            if category:
                search_query = f"{search_query} {category}"
            if language and language != "English":
                search_query = f"{search_query} {language}"
            playlists = search_youtube_playlists(search_query, lang_code, 12, min_videos=5)

            if not playlists:
                messages.info(request, "No playlists found. Try a different search or filter.")

        except Exception as e:
            print("Search error:", repr(e))
            messages.error(request, "Could not load YouTube results right now.")
    elif form_submitted:
        messages.error(request, "Please enter a search term or select a filter.")
    else:
        try:
            trending_queries = [
                "programming tutorial",
                "data science",
                "web development",
                "machine learning",
                "python tutorial",
                "javascript tutorial",
            ]
            trending_q = random.choice(trending_queries)
            playlists = search_youtube_playlists(trending_q, "", 8, min_videos=5)
            is_trending = True
        except Exception as e:
            print("Trending error:", repr(e))

    return render(request, "search.html", {
        "playlists": playlists,
        "query": query,
        "is_trending": is_trending,
    })

def search_run_stub(request: HttpRequest) -> HttpResponse:
    query = (request.POST.get("q") or "").strip()
    if not query:
        messages.error(request, "Please enter a search keyword.")
        return redirect("search")
    return redirect(f"/search/?q={query}")


def course_detail_page(request: HttpRequest) -> HttpResponse:
    ensure_project_tables()

    playlist_id = (request.GET.get("playlist_id") or "").strip()
    yt_playlist_id = (request.GET.get("yt_playlist_id") or "").strip()
    playlist = None
    videos = []

    if yt_playlist_id:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT playlist_id
                FROM playlists
                WHERE youtube_playlist_id = %s
            """, [yt_playlist_id])
            row = cursor.fetchone()

        if row:
            return redirect(f"/course-detail/?playlist_id={row[0]}")

        yt_videos = get_playlist_videos(yt_playlist_id)
        if not yt_videos:
            messages.info(request, "This playlist has no embeddable videos.")
            return redirect("search")

        first_video = yt_videos[0]
        channel_id = first_video.get("channel_id", "YT_CHANNEL")
        channel_name = first_video.get("channel", "YouTube Channel")

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT creator_id FROM creators WHERE youtube_channel_id = %s
            """, [channel_id])
            crow = cursor.fetchone()

            if crow:
                creator_id = crow[0]
            else:
                cursor.execute("""
                    INSERT INTO creators (youtube_channel_id, creator_name, channel_name, description, subscriber_count)
                    VALUES (%s, %s, %s, %s, %s)
                """, [channel_id, channel_name, channel_name, "", 0])
                creator_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO playlists (
                    creator_id, youtube_playlist_id, title, description,
                    thumbnail_url, language, level, video_count,
                    total_duration_seconds, total_views, completion_score, is_complete_candidate
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, [
                creator_id, yt_playlist_id,
                first_video.get("title", "YouTube Playlist"),
                first_video.get("description", "")[:500],
                first_video.get("thumbnail", ""),
                "", "", len(yt_videos), 0, 0, 0.00, 0,
            ])
            db_playlist_id = cursor.lastrowid

            for idx, vid in enumerate(yt_videos):
                embed_url = f"https://www.youtube.com/embed/{vid['video_id']}"
                cursor.execute("""
                    INSERT INTO videos (
                        playlist_id, creator_id, youtube_video_id, title, description,
                        embed_url, thumbnail_url, duration_seconds, views_count, likes_count, playlist_order
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, [
                    db_playlist_id, creator_id, vid["video_id"],
                    vid["title"], vid["description"],
                    embed_url, vid["thumbnail"],
                    0, vid["views"], 0, idx + 1,
                ])

        return redirect(f"/course-detail/?playlist_id={db_playlist_id}")

    if playlist_id:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT playlist_id, title, description, thumbnail_url, language, level
                FROM playlists
                WHERE playlist_id = %s
            """, [playlist_id])
            row = cursor.fetchone()

            if row:
                playlist = {
                    "playlist_id": row[0],
                    "title": row[1],
                    "description": row[2],
                    "thumbnail_url": row[3],
                    "language": row[4],
                    "level": row[5],
                }

            cursor.execute("""
                SELECT video_id, youtube_video_id, title, description, thumbnail_url, playlist_order
                FROM videos
                WHERE playlist_id = %s
                ORDER BY playlist_order
            """, [playlist_id])
            rows = cursor.fetchall()

        videos = [{
            "video_id": row[0],
            "youtube_video_id": row[1],
            "title": row[2],
            "description": row[3],
            "thumbnail_url": row[4],
            "playlist_order": row[5],
        } for row in rows]

    else:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT playlist_id, title, description, thumbnail_url, language, level
                FROM playlists
                ORDER BY created_at DESC
                LIMIT 1
            """)
            row = cursor.fetchone()

        if row:
            return redirect(f"/course-detail/?playlist_id={row[0]}")

    return render(request, "course_detail.html", {
        "playlist": playlist,
        "videos": videos,
    })


def video_player_page(request: HttpRequest) -> HttpResponse:
    ensure_project_tables()

    youtube_video_id = (request.GET.get("video_id") or "").strip()
    internal_video_id = (request.GET.get("db_video_id") or "").strip()

    current = None
    next_video = None
    reviews = []
    progress_percent = 0
    module_num = 1
    total_modules = 1
    playlist_videos = []
    upcoming_videos = []

    if youtube_video_id:
        current = get_db_video_by_youtube_id(youtube_video_id)
    elif internal_video_id.isdigit():
        current = get_db_video_by_internal_id(int(internal_video_id))

    if not current:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT video_id
                FROM videos
                ORDER BY created_at DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
        if row:
            current = get_db_video_by_internal_id(row[0])

    if not current:
        messages.info(request, "No video available yet. Please search first.")
        return redirect("search")

    current["embed_url"] = f"https://www.youtube.com/embed/{current['youtube_video_id']}"

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*)
            FROM videos
            WHERE playlist_id = %s
        """, [current["playlist_id"]])
        total_modules = cursor.fetchone()[0] or 1

        cursor.execute("""
            SELECT video_id, youtube_video_id, title, description, thumbnail_url, playlist_order
            FROM videos
            WHERE playlist_id = %s
            ORDER BY playlist_order
        """, [current["playlist_id"]])
        rows = cursor.fetchall()

        playlist_videos = [{
            "video_id": row[0],
            "youtube_video_id": row[1],
            "title": row[2],
            "description": row[3],
            "thumbnail_url": row[4],
            "playlist_order": row[5],
        } for row in rows]

        cursor.execute("""
            SELECT video_id, youtube_video_id, title
            FROM videos
            WHERE playlist_id = %s AND playlist_order > %s
            ORDER BY playlist_order
        """, [current["playlist_id"], current["playlist_order"]])
        upcoming_rows = cursor.fetchall()

        upcoming_videos = [{
            "video_id": row[0],
            "youtube_video_id": row[1],
            "title": row[2],
        } for row in upcoming_rows]

        if upcoming_videos:
            next_video = upcoming_videos[0]

    module_num = current["playlist_order"]
    progress_percent = round((module_num / total_modules) * 100) if total_modules else 0

    if request.user.is_authenticated:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT history_paused FROM user_settings WHERE user_id = %s",
                [request.user.id],
            )
            settings_row = cursor.fetchone()
            history_paused = bool(settings_row[0]) if settings_row else False

            if not history_paused:
                cursor.execute("""
                    INSERT INTO watch_history (user_id, video_id)
                    VALUES (%s, %s)
                """, [request.user.id, current["video_id"]])

            if current["playlist_order"] > 1:
                cursor.execute("""
                    SELECT video_id FROM videos
                    WHERE playlist_id = %s AND playlist_order = %s
                """, [current["playlist_id"], current["playlist_order"] - 1])
                prev_row = cursor.fetchone()
                if prev_row:
                    cursor.execute("""
                        UPDATE video_progress
                        SET progress_percent = 100.00, is_completed = 1,
                            last_watched_at = CURRENT_TIMESTAMP
                        WHERE user_id = %s AND video_id = %s
                    """, [request.user.id, prev_row[0]])

            cursor.execute("""
                SELECT progress_id
                FROM video_progress
                WHERE user_id = %s AND video_id = %s
            """, [request.user.id, current["video_id"]])
            row = cursor.fetchone()

            if not row:
                cursor.execute("""
                    INSERT INTO video_progress (
                        user_id, video_id, watched_seconds, progress_percent, is_completed
                    ) VALUES (%s, %s, %s, %s, %s)
                """, [request.user.id, current["video_id"], 0, 0.00, 0])

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT r.review_id, r.rating, r.comment, r.created_at, u.first_name, u.username
                FROM reviews r
                LEFT JOIN auth_user u ON r.user_id = u.id
                WHERE r.video_id = %s
                ORDER BY r.created_at DESC
            """, [current["video_id"]])
            rows = cursor.fetchall()

        reviews = [{
            "review_id": row[0],
            "rating": row[1],
            "comment": row[2],
            "created_at": row[3],
            "user_name": row[4] or row[5] or "User",
        } for row in rows]
    except Exception as e:
        print("Reviews query error:", repr(e))

    is_liked = False
    if request.user.is_authenticated:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT like_id FROM liked_videos
                WHERE user_id = %s AND video_id = %s
            """, [request.user.id, current["video_id"]])
            is_liked = cursor.fetchone() is not None

    return render(request, "video_player.html", {
    "playlist": playlist_videos,
    "current": current,
    "module_num": module_num,
    "total_modules": total_modules,
    "progress_percent": progress_percent,
    "up_next": upcoming_videos,
    "reviews": reviews,
    "next_video": next_video,
    "is_liked": is_liked,
})


# ---------------------------
# Reviews / Likes / Progress
# ---------------------------

def review_submit_stub(request: HttpRequest) -> HttpResponse:
    ensure_project_tables()

    if not request.user.is_authenticated:
        messages.error(request, "Please sign in to submit a review.")
        return redirect("login")

    if request.method != "POST":
        return redirect("video_player")

    video_id = (request.POST.get("video_id") or "").strip()
    youtube_video_id = (request.POST.get("youtube_video_id") or "").strip()
    rating = (request.POST.get("rating") or "").strip()
    comment = (request.POST.get("comment") or "").strip()

    db_video = None
    if video_id.isdigit():
        db_video = get_db_video_by_internal_id(int(video_id))
    elif youtube_video_id:
        db_video = get_db_video_by_youtube_id(youtube_video_id)

    if not db_video:
        messages.error(request, "Video not found for review.")
        return redirect("search")

    if not comment:
        messages.error(request, "Please write your comment.")
        return redirect(f"/video_player/?db_video_id={db_video['video_id']}")

    numeric_rating = None
    if rating:
        try:
            numeric_rating = int(rating)
        except ValueError:
            numeric_rating = None

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO reviews (user_id, video_id, rating, comment)
                VALUES (%s, %s, %s, %s)
            """, [request.user.id, db_video["video_id"], numeric_rating, comment])
        messages.success(request, "Review submitted successfully.")
    except Exception as e:
        print("Review insert error:", repr(e))
        messages.error(request, "Could not save your review. Please try again.")

    return redirect(f"/video_player/?db_video_id={db_video['video_id']}")


def like_video_toggle(request: HttpRequest) -> HttpResponse:
    ensure_project_tables()

    if not request.user.is_authenticated:
        messages.error(request, "Please sign in to like videos.")
        return redirect("login")

    video_id = (request.POST.get("video_id") or "").strip()
    youtube_video_id = (request.POST.get("youtube_video_id") or "").strip()

    db_video = None
    if video_id.isdigit():
        db_video = get_db_video_by_internal_id(int(video_id))
    elif youtube_video_id:
        db_video = get_db_video_by_youtube_id(youtube_video_id)

    if not db_video:
        messages.error(request, "Video not found.")
        return redirect("search")

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT like_id
            FROM liked_videos
            WHERE user_id = %s AND video_id = %s
        """, [request.user.id, db_video["video_id"]])
        row = cursor.fetchone()

        if row:
            cursor.execute("""
                DELETE FROM liked_videos
                WHERE like_id = %s
            """, [row[0]])
            messages.info(request, "Video removed from liked videos.")
        else:
            cursor.execute("""
                INSERT INTO liked_videos (user_id, video_id)
                VALUES (%s, %s)
            """, [request.user.id, db_video["video_id"]])
            messages.success(request, "Video added to liked videos.")

    return redirect(f"/video_player/?db_video_id={db_video['video_id']}")


def mark_progress(request: HttpRequest) -> HttpResponse:
    ensure_project_tables()

    if not request.user.is_authenticated:
        messages.error(request, "Please sign in to update progress.")
        return redirect("login")

    video_id = (request.POST.get("video_id") or "").strip()
    watched_seconds = (request.POST.get("watched_seconds") or "0").strip()
    progress_percent = (request.POST.get("progress_percent") or "0").strip()
    is_completed = 1 if request.POST.get("is_completed") else 0

    if not video_id.isdigit():
        messages.error(request, "Invalid video.")
        return redirect("progress")

    try:
        watched_seconds = int(watched_seconds)
    except ValueError:
        watched_seconds = 0

    try:
        progress_percent = float(progress_percent)
    except ValueError:
        progress_percent = 0.0

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT progress_id
            FROM video_progress
            WHERE user_id = %s AND video_id = %s
        """, [request.user.id, int(video_id)])
        row = cursor.fetchone()

        if row:
            cursor.execute("""
                UPDATE video_progress
                SET watched_seconds = %s,
                    progress_percent = %s,
                    is_completed = %s,
                    last_watched_at = CURRENT_TIMESTAMP
                WHERE progress_id = %s
            """, [watched_seconds, progress_percent, is_completed, row[0]])
        else:
            cursor.execute("""
                INSERT INTO video_progress (
                    user_id, video_id, watched_seconds, progress_percent, is_completed
                ) VALUES (%s, %s, %s, %s, %s)
            """, [request.user.id, int(video_id), watched_seconds, progress_percent, is_completed])

    messages.success(request, "Progress updated.")
    return redirect("progress")


def progress_page(request: HttpRequest) -> HttpResponse:
    ensure_project_tables()

    if not request.user.is_authenticated:
        messages.info(request, "Please sign in to view progress.")
        return redirect("login")

    progress_items = []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT vp.progress_id, vp.video_id, v.title, v.youtube_video_id, vp.watched_seconds,
                       vp.progress_percent, vp.is_completed, vp.last_watched_at
                FROM video_progress vp
                JOIN videos v ON vp.video_id = v.video_id
                WHERE vp.user_id = %s
                ORDER BY vp.last_watched_at DESC
            """, [request.user.id])
            rows = cursor.fetchall()

        progress_items = [{
            "progress_id": row[0],
            "video_id": row[1],
            "title": row[2],
            "youtube_video_id": row[3],
            "watched_seconds": row[4],
            "progress_percent": row[5],
            "is_completed": row[6],
            "last_watched_at": row[7],
        } for row in rows]
    except Exception as e:
        print("Progress query error:", repr(e))
        messages.error(request, "Could not load your progress data right now.")

    total_watched_seconds = sum(item["watched_seconds"] or 0 for item in progress_items)
    hours_studied = round(total_watched_seconds / 3600, 1)
    completed_count = sum(1 for item in progress_items if item["is_completed"])
    total_videos = len(progress_items)
    overall_percent = round((completed_count / total_videos) * 100) if total_videos else 0

    return render(request, "progress.html", {
        "progress_items": progress_items,
        "hours_studied": hours_studied,
        "completed_count": completed_count,
        "total_videos": total_videos,
        "overall_percent": overall_percent,
    })


# ---------------------------
# Profile / History
# ---------------------------

def profile_page(request: HttpRequest) -> HttpResponse:
    ensure_project_tables()

    if not request.user.is_authenticated:
        messages.info(request, "Please sign in to view your profile.")
        return redirect("login")

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT lv.like_id, v.video_id, v.youtube_video_id, v.title, v.thumbnail_url, lv.liked_at
            FROM liked_videos lv
            JOIN videos v ON lv.video_id = v.video_id
            WHERE lv.user_id = %s
            ORDER BY lv.liked_at DESC
        """, [request.user.id])
        liked_rows = cursor.fetchall()

        cursor.execute("""
            SELECT wh.history_id, v.video_id, v.youtube_video_id, v.title, v.thumbnail_url, wh.watched_at
            FROM watch_history wh
            JOIN videos v ON wh.video_id = v.video_id
            WHERE wh.user_id = %s
            ORDER BY wh.watched_at DESC
            LIMIT 20
        """, [request.user.id])
        history_rows = cursor.fetchall()

    liked_videos = [{
        "like_id": row[0],
        "video_id": row[1],
        "youtube_video_id": row[2],
        "title": row[3],
        "thumbnail_url": row[4],
        "liked_at": row[5],
    } for row in liked_rows]

    watch_history = [{
        "history_id": row[0],
        "video_id": row[1],
        "youtube_video_id": row[2],
        "title": row[3],
        "thumbnail_url": row[4],
        "watched_at": row[5],
    } for row in history_rows]

    return render(request, "profile.html", {
        "liked_videos": liked_videos,
        "watch_history": watch_history,
    })


def watch_history_stub(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        messages.info(request, "Please sign in to view watch history.")
        return redirect("login")
    return redirect("profile")


def in_progress_stub(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        messages.info(request, "Please sign in to view in-progress videos.")
        return redirect("login")
    return redirect("progress")

def clear_videos(request: HttpRequest) -> HttpResponse:
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM reviews")
        cursor.execute("DELETE FROM liked_videos")
        cursor.execute("DELETE FROM watch_history")
        cursor.execute("DELETE FROM video_progress")
        cursor.execute("DELETE FROM user_settings")
        cursor.execute("DELETE FROM videos")
        cursor.execute("DELETE FROM playlists")
        cursor.execute("DELETE FROM creators")
    return HttpResponse("All video data cleared successfully.")


def settings_page(request: HttpRequest) -> HttpResponse:
    ensure_project_tables()

    if not request.user.is_authenticated:
        messages.info(request, "Please sign in to access settings.")
        return redirect("login")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT history_paused FROM user_settings WHERE user_id = %s",
            [request.user.id],
        )
        row = cursor.fetchone()
        history_paused = bool(row[0]) if row else False

    return render(request, "settings.html", {
        "history_paused": history_paused,
    })


def update_name(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")

    if request.method == "POST":
        new_name = (request.POST.get("first_name") or "").strip()
        if new_name:
            request.user.first_name = new_name
            request.user.save()
            messages.success(request, "Name updated successfully.")
        else:
            messages.error(request, "Name cannot be empty.")

    return redirect("settings")


def toggle_history(request: HttpRequest) -> HttpResponse:
    ensure_project_tables()

    if not request.user.is_authenticated:
        return redirect("login")

    if request.method == "POST":
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT history_paused FROM user_settings WHERE user_id = %s",
                [request.user.id],
            )
            row = cursor.fetchone()
            if row:
                new_val = 0 if row[0] else 1
                cursor.execute(
                    "UPDATE user_settings SET history_paused = %s WHERE user_id = %s",
                    [new_val, request.user.id],
                )
            else:
                cursor.execute(
                    "INSERT INTO user_settings (user_id, history_paused) VALUES (%s, 1)",
                    [request.user.id],
                )
        paused = not bool(row[0]) if row else True
        if paused:
            messages.success(request, "Watch history paused.")
        else:
            messages.success(request, "Watch history resumed.")

    return redirect("settings")


def delete_account(request: HttpRequest) -> HttpResponse:
    ensure_project_tables()

    if not request.user.is_authenticated:
        return redirect("login")

    if request.method == "POST":
        uid = request.user.id
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM reviews WHERE user_id = %s", [uid])
            cursor.execute("DELETE FROM liked_videos WHERE user_id = %s", [uid])
            cursor.execute("DELETE FROM watch_history WHERE user_id = %s", [uid])
            cursor.execute("DELETE FROM video_progress WHERE user_id = %s", [uid])
            cursor.execute("DELETE FROM user_settings WHERE user_id = %s", [uid])
        request.user.delete()
        logout(request)
        messages.success(request, "Your account has been deleted.")
        return redirect("login")

    return redirect("settings")