import os
import requests

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

API_TIMEOUT = 10


def search_youtube_playlists(query, language_code="", max_results=12, min_videos=5):
    try:
        search_url = "https://www.googleapis.com/youtube/v3/search"
        search_params = {
            "part": "snippet",
            "q": query,
            "type": "playlist",
            "maxResults": max_results,
            "key": YOUTUBE_API_KEY,
        }

        if language_code:
            search_params["relevanceLanguage"] = language_code

        search_response = requests.get(search_url, params=search_params, timeout=API_TIMEOUT)
        search_data = search_response.json()

        playlists = []
        pl_ids = []
        for item in search_data.get("items", []):
            playlist_id = item.get("id", {}).get("playlistId")
            snippet = item.get("snippet", {})

            if not playlist_id:
                continue

            pl_ids.append(playlist_id)
            playlists.append({
                "playlist_id": playlist_id,
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                "channel": snippet.get("channelTitle", ""),
                "channel_id": snippet.get("channelId", ""),
                "video_count": 0,
                "views": 0,
            })

        if not pl_ids:
            return []

        details_resp = requests.get(
            "https://www.googleapis.com/youtube/v3/playlists",
            params={
                "part": "contentDetails",
                "id": ",".join(pl_ids),
                "key": YOUTUBE_API_KEY,
            },
            timeout=API_TIMEOUT,
        )
        details_data = details_resp.json()

        count_map = {}
        for item in details_data.get("items", []):
            pid = item.get("id")
            count_map[pid] = item.get("contentDetails", {}).get("itemCount", 0)

        for pl in playlists:
            pl["video_count"] = count_map.get(pl["playlist_id"], 0)

        playlists = [pl for pl in playlists if pl["video_count"] >= min_videos]

        if not playlists:
            return playlists

        first_video_ids = {}
        for pl in playlists:
            resp = requests.get(
                "https://www.googleapis.com/youtube/v3/playlistItems",
                params={
                    "part": "snippet",
                    "playlistId": pl["playlist_id"],
                    "maxResults": 1,
                    "key": YOUTUBE_API_KEY,
                },
                timeout=API_TIMEOUT,
            )
            data = resp.json()
            items = data.get("items", [])
            if items:
                vid = items[0].get("snippet", {}).get("resourceId", {}).get("videoId")
                if vid:
                    first_video_ids[pl["playlist_id"]] = vid

        all_vids = list(set(first_video_ids.values()))
        views_map = {}
        if all_vids:
            for i in range(0, len(all_vids), 50):
                batch = all_vids[i : i + 50]
                resp = requests.get(
                    "https://www.googleapis.com/youtube/v3/videos",
                    params={
                        "part": "statistics",
                        "id": ",".join(batch),
                        "key": YOUTUBE_API_KEY,
                    },
                    timeout=API_TIMEOUT,
                )
                for item in resp.json().get("items", []):
                    views_map[item["id"]] = int(
                        item.get("statistics", {}).get("viewCount", 0)
                    )

        for pl in playlists:
            vid = first_video_ids.get(pl["playlist_id"])
            if vid:
                pl["views"] = views_map.get(vid, 0)

        playlists.sort(key=lambda p: p["views"], reverse=True)
        return playlists

    except requests.RequestException as e:
        print("YouTube API request error in search_youtube_playlists:", repr(e))
        return []
    except Exception as e:
        print("Unexpected error in search_youtube_playlists:", repr(e))
        return []


def get_playlist_videos(youtube_playlist_id):
    try:
        items = []
        page_token = None

        while True:
            params = {
                "part": "snippet,status",
                "playlistId": youtube_playlist_id,
                "maxResults": 50,
                "key": YOUTUBE_API_KEY,
            }
            if page_token:
                params["pageToken"] = page_token

            resp = requests.get(
                "https://www.googleapis.com/youtube/v3/playlistItems",
                params=params,
                timeout=API_TIMEOUT,
            )
            data = resp.json()
            items.extend(data.get("items", []))

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        video_ids = []
        position_map = {}
        for item in items:
            snippet = item.get("snippet", {})
            vid = snippet.get("resourceId", {}).get("videoId")
            if not vid:
                continue
            video_ids.append(vid)
            position_map[vid] = snippet.get("position", 0)

        if not video_ids:
            return []

        videos = []
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            details_resp = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "snippet,statistics,status",
                    "id": ",".join(batch),
                    "key": YOUTUBE_API_KEY,
                },
                timeout=API_TIMEOUT,
            )
            details_data = details_resp.json()

            for item in details_data.get("items", []):
                vid = item.get("id")
                status = item.get("status", {})
                if not status.get("embeddable", False):
                    continue

                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                videos.append({
                    "video_id": vid,
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                    "channel": snippet.get("channelTitle", ""),
                    "channel_id": snippet.get("channelId", ""),
                    "views": int(stats.get("viewCount", 0)),
                    "position": position_map.get(vid, 0),
                })

        videos.sort(key=lambda v: v["position"])
        return videos

    except requests.RequestException as e:
        print("YouTube API request error in get_playlist_videos:", repr(e))
        return []
    except Exception as e:
        print("Unexpected error in get_playlist_videos:", repr(e))
        return []
