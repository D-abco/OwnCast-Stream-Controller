import os
import queue
import time
import json
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

with open(os.path.join(os.path.dirname(__file__), '..', 'config.json'), 'r') as f:
    config = json.load(f)

API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
GOOGLE_CLIENT_ID = config.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = config.get("GOOGLE_CLIENT_SECRET")
PLAYLIST_ID = config.get("YOUTUBE_PLAYLIST_ID")

# For background playlist additions
playlist_add_queue = queue.Queue()
clients = []

def credentials_to_dict(credentials):
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

def get_youtube(session):
    if 'credentials' not in session:
        return None
    creds = Credentials.from_authorized_user_info(session['credentials'])
    return build(API_SERVICE_NAME, API_VERSION, credentials=creds)

def get_service_youtube():
    """Get a YouTube API client using a persistent token.json for background tasks."""
    if not os.path.exists("token.json"):
        print("No token.json found for service account.")
        return None
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    return build(API_SERVICE_NAME, API_VERSION, credentials=creds)

def extract_youtube_id(url):
    import re
    match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return match.group(1) if match else None

def add_video_to_playlist(youtube, video_id):
    try:
        video_response = youtube.videos().list(
            part='snippet',
            id=video_id
        ).execute()

        if not video_response['items']:
            print(f"❌ Invalid or non-existent video ID: {video_id}")
            return False, "Invalid or non-existent video ID"

        video_snippet = video_response['items'][0]['snippet']
        video_title = video_snippet['title']
        video_thumbnail_url = video_snippet['thumbnails']['default']['url']

        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": PLAYLIST_ID,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id
                    }
                }
            }
        ).execute()
        print(f"✅ Video {video_id} added to playlist!")
        return True, {
            "video_id": video_id,
            "title": video_title,
            "thumbnail": video_thumbnail_url
        }
    except Exception as e:
        print(f"❌ Error adding video: {e}")
        return False, str(e)

def clear_playlist(youtube):
    try:
        items = []
        nextPageToken = None
        while True:
            pl_items = youtube.playlistItems().list(
                part="id",
                playlistId=PLAYLIST_ID,
                maxResults=50,
                pageToken=nextPageToken
            ).execute()
            items.extend(pl_items.get("items", []))
            nextPageToken = pl_items.get("nextPageToken")
            if not nextPageToken:
                break

        for item in items:
            youtube.playlistItems().delete(id=item["id"]).execute()
        print("✅ Playlist cleared!")
        return True, "Playlist cleared"
    except Exception as e:
        print(f"❌ Error clearing playlist: {e}")
        return False, str(e)

def get_playlist_items(youtube):
    playlist_items = []
    nextPageToken = None
    while True:
        request_playlist_items = youtube.playlistItems().list(
            part="snippet",
            playlistId=PLAYLIST_ID,
            maxResults=50,
            pageToken=nextPageToken
        )
        response = request_playlist_items.execute()
        for item in response["items"]:
            snippet = item["snippet"]
            video_id = snippet["resourceId"]["videoId"]
            title = snippet["title"]
            thumbnail = snippet["thumbnails"].get("medium", {}).get("url") \
                or snippet["thumbnails"].get("high", {}).get("url") \
                or snippet["thumbnails"].get("default", {}).get("url", "")

            playlist_items.append({
                "title": title,
                "video_id": video_id,
                "thumbnail": thumbnail
            })
        nextPageToken = response.get("nextPageToken")
        if not nextPageToken:
            break
    return playlist_items

def skip_current_video(youtube, current_video_id):
    items = []
    nextPageToken = None
    while True:
        pl_items = youtube.playlistItems().list(
            part="id,snippet",
            playlistId=PLAYLIST_ID,
            maxResults=50,
            pageToken=nextPageToken
        ).execute()
        items.extend(pl_items.get("items", []))
        nextPageToken = pl_items.get("nextPageToken")
        if not nextPageToken:
            break

    to_remove = None
    for item in items:
        vid = item["snippet"]["resourceId"]["videoId"]
        if vid == current_video_id:
            to_remove = item["id"]
            break

    if not to_remove and items:
        to_remove = items[0]["id"]

    if not to_remove:
        print("No video to skip.")
        return False, "No video to skip."

    youtube.playlistItems().delete(id=to_remove).execute()
    print("⏭️ Skipped!")
    return True, "Skipped"

def playlist_add_worker():
    while True:
        video_id = playlist_add_queue.get()
        youtube = get_service_youtube()
        if not youtube:
            print("Not authorized to add video (service account).")
            playlist_add_queue.task_done()
            continue
        try:
            add_video_to_playlist(youtube, video_id)
        except Exception as e:
            print(f"❌ Error adding video: {e}")
        playlist_add_queue.task_done()