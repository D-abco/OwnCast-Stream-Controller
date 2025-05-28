import os
import time
import queue
import json
import re
import subprocess
from threading import Thread, Lock
from flask import Flask, redirect, url_for, session, request, render_template, jsonify, Response
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from obswebsocket import obsws, requests as obs_requests
import sseclient
from PIL import Image

from features.superchat import superchat_queue, start_superchat_worker
from features.bounce import bounce_queue, start_bounce_worker
from features.brainrot import start_brainrot_worker
from features.youtube import (
    get_youtube, get_service_youtube, add_video_to_playlist, clear_playlist,
    get_playlist_items, skip_current_video, extract_youtube_id,
    playlist_add_queue, playlist_add_worker, PLAYLIST_ID, credentials_to_dict
)

# Flask app setup
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

with open('config.json', 'r') as f:
    config = json.load(f)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email"
]

OBS_Host = config.get('OBS_Host')
OBS_Port = config.get('OBS_Port')
OBS_Password = config.get('OBS_Password')
app_secret_key = config.get('FLASK_SECRET_KEY')
if not app_secret_key or app_secret_key == 'changeme':
    raise RuntimeError("FLASK_SECRET_KEY must be set in config.json and not be 'changeme'")
GOOGLE_CLIENT_ID = config.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = config.get('GOOGLE_CLIENT_SECRET')
PLAYLIST_ID = config.get('YOUTUBE_PLAYLIST_ID')

app = Flask(__name__)
app.secret_key = app_secret_key

queue_lock = Lock()
clients = []

# Start feature workers
start_superchat_worker(OBS_Host, OBS_Port, OBS_Password)
start_bounce_worker(OBS_Host, OBS_Port, OBS_Password)
handle_brainrot_event = start_brainrot_worker(OBS_Host, OBS_Port, OBS_Password)
Thread(target=playlist_add_worker, daemon=True).start()

# SSE Listener
def sse_listener():
    url = "https://stream.planetfifty.one/events"
    print("Connecting to SSE stream...")
    client = sseclient.SSEClient(url)
    for event in client:
        try:
            data = json.loads(event.data)
            event_type = data.get("type")
            event_data = data.get("eventData", {})
            redeem = event_data.get("redeem")

            if redeem == "superchat" and event_type in ("TLAPBOT_REDEEM_NOTE_SUCCESS", "TLAPBOT_REDEEM_LIST_SUCCESS"):
                note = event_data.get("note", "")
                display_name = event_data.get("display_name", "")
                if note:
                    superchat_queue.put((display_name, note))
                    print(f"Queued superchat from {display_name}: {note}")

            elif redeem == "play" and event_type in ("TLAPBOT_REDEEM_NOTE_SUCCESS", "TLAPBOT_REDEEM_LIST_SUCCESS"):
                custom_message = event_data.get("custom_message", "")
                url_match = re.search(r"(https?://[^\s]+)", custom_message)
                if url_match:
                    youtube_url = url_match.group(1)
                    video_id = extract_youtube_id(youtube_url)
                    if video_id:
                        print(f"Adding video from play redeem: {video_id}")
                        playlist_add_queue.put(video_id)
                    else:
                        print("Could not extract video ID from URL:", youtube_url)

            elif redeem == "brainrot" and event_type in ("TLAPBOT_REDEEM_NOTE_SUCCESS", "TLAPBOT_REDEEM_LIST_SUCCESS"):
                handle_brainrot_event()

            elif redeem == "bounce" and event_type in ("TLAPBOT_REDEEM_NOTE_SUCCESS", "TLAPBOT_REDEEM_LIST_SUCCESS"):
                image_url = (
                    event_data.get("note")
                    or event_data.get("custom_message")
                    or event_data.get("full_message")
                )
                url_match = re.search(r"(https?://[^\s]+)", image_url or "")
                if url_match:
                    image_url = url_match.group(1)
                if image_url:
                    print(f"Queued bounce image: {image_url}")
                    bounce_queue.put(image_url)
        except Exception as e:
            print("SSE message error:", e)

Thread(target=sse_listener, daemon=True).start()

# Playlist update notification
def notify_playlist_update():
    for client in clients:
        client.put("playlist_updated")

# Now playing state
now_playing_state = {
    "video_id": "",
    "title": "",
    "thumbnail": "",
    "duration": 0,
    "start_time": 0,
    "elapsed": 0,
    "paused": False
}

# Flask routes
@app.route('/')
def index():
    if 'credentials' not in session:
        return redirect(url_for('authorize'))
    youtube = get_youtube(session)
    if not youtube:
        return redirect(url_for('authorize'))
    playlist_items = get_playlist_items(youtube)
    return render_template("index.html", videos=playlist_items)

@app.route('/authorize')
def authorize():
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uris": ["http://localhost:5000/oauth2callback"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        },
        scopes=SCOPES,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    auth_url, _ = flow.authorization_url(prompt='consent')
    return redirect(auth_url)

@app.route('/oauth2callback')
def oauth2callback():
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uris": ["http://localhost:5000/oauth2callback"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        },
        scopes=SCOPES,
        redirect_uri="http://localhost:5000/oauth2callback"
    )
    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials

    with open("token.json", "w") as token:
        token.write(credentials.to_json())

    session['credentials'] = credentials_to_dict(credentials)

    return redirect(url_for('index'))

@app.route('/add_video', methods=['POST'])
def add_video():
    if 'credentials' not in session:
        return jsonify({"message": "Not authorized"}), 401
    youtube = get_youtube(session)
    if not youtube:
        return jsonify({"message": "Not authorized"}), 401
    video_id = request.json.get('video_id') if request.is_json else request.form.get('video_id')
    if not video_id:
        return jsonify({ "message": "❌ Missing video ID" }), 400
    success, result = add_video_to_playlist(youtube, video_id)
    if not success:
        return jsonify({ "message": f"❌ {result}" }), 400
    notify_playlist_update()
    return jsonify({
        "message": "✅ Video added!",
        "video": result
    }), 200

@app.route('/clear_playlist', methods=['POST'])
def clear_playlist_route():
    if 'credentials' not in session:
        return jsonify({"message": "Not authorized"}), 401
    youtube = get_youtube(session)
    if not youtube:
        return jsonify({"message": "Not authorized"}), 401
    success, result = clear_playlist(youtube)
    if not success:
        return jsonify({"message": f"❌ {result}"}), 500
    notify_playlist_update()
    return jsonify({"message": "✅ Playlist cleared!"}), 200

@app.route('/api/playlist')
def api_playlist():
    if 'credentials' not in session:
        return jsonify([]), 401
    youtube = get_youtube(session)
    if not youtube:
        return jsonify([]), 401
    playlist_items = get_playlist_items(youtube)
    return jsonify(playlist_items)

@app.route('/playlist_events')
def playlist_events():
    def event_stream():
        messages = queue.Queue()
        clients.append(messages)
        try:
            while True:
                msg = messages.get()
                yield f"data: {msg}\n\n"
        except GeneratorExit:
            clients.remove(messages)
    return Response(event_stream(), mimetype="text/event-stream")

@app.route('/set_now_playing', methods=['POST'])
def set_now_playing():
    data = request.json
    action = data.get("action", "play")
    if action == "play":
        if data["video_id"] != now_playing_state["video_id"]:
            now_playing_state.update({
                "video_id": data["video_id"],
                "title": data["title"],
                "thumbnail": data["thumbnail"],
                "duration": data["duration"],
                "start_time": time.time(),
                "elapsed": data.get("position", 0),
                "paused": False
            })
        elif now_playing_state["paused"]:
            now_playing_state["start_time"] = time.time()
            now_playing_state["paused"] = False
    elif action == "pause":
        if not now_playing_state["paused"]:
            now_playing_state["elapsed"] += time.time() - now_playing_state["start_time"]
            now_playing_state["paused"] = True
    elif action == "seek":
        now_playing_state["elapsed"] = data.get("position", 0)
        now_playing_state["start_time"] = time.time()
    return '', 204

@app.route('/now_playing')
def now_playing():
    return jsonify(now_playing_state)

@app.route('/now_playing_overlay')
def now_playing_overlay():
    return render_template("now_playing.html")

@app.route('/run_test/<test_name>', methods=['POST'])
def run_test(test_name):
    scripts = {
        "superchattest": "tests/superchattest.py",
        "bouncetest": "tests/bouncetest.py",
        "brainrot": "tests/brainrottest.py",
        "youtubetest": "tests/youtubetest.py"
    }
    script = scripts.get(test_name)
    if not script:
        return jsonify({"message": "Unknown test script."}), 400
    try:
        result = subprocess.run(
            ["python3", script],
            capture_output=True, text=True, timeout=30
        )
        return jsonify({
            "output": result.stdout.strip() or "(No output)",
            "error": result.stderr.strip(),
            "returncode": result.returncode
        })
    except Exception as e:
        return jsonify({"message": f"Error running script: {e}"}), 500

@app.route('/skip', methods=['POST'])
def skip():
    if 'credentials' not in session:
        return jsonify({"message": "Not authorized"}), 401
    youtube = get_youtube(session)
    if not youtube:
        return jsonify({"message": "Not authorized"}), 401
    current_video_id = now_playing_state.get("video_id")
    success, result = skip_current_video(youtube, current_video_id)
    if not success:
        return jsonify({"message": result}), 400
    notify_playlist_update()
    return jsonify({"message": "⏭️ Skipped!"}), 200

@app.route('/test_event', methods=['POST'])
def test_event():
    data = request.get_json()
    event_type = data.get("type")
    event_data = data.get("eventData", {})
    redeem = event_data.get("redeem")

    if redeem == "superchat":
        note = event_data.get("note", "")
        display_name = event_data.get("display_name", "")
        if note:
            superchat_queue.put((display_name, note))
            return jsonify({"message": "Superchat test event queued"}), 200

    elif redeem == "bounce":
        image_url = (
            event_data.get("note")
            or event_data.get("custom_message")
            or event_data.get("full_message")
        )
        if image_url:
            bounce_queue.put(image_url)
            return jsonify({"message": "Bounce test event queued"}), 200

    elif redeem == "brainrot":
        handle_brainrot_event()
        return jsonify({"message": "Brainrot test event triggered"}), 200

    elif redeem == "play":
        custom_message = event_data.get("custom_message", "")
        url_match = re.search(r"(https?://[^\s]+)", custom_message)
        if url_match:
            youtube_url = url_match.group(1)
            video_id = extract_youtube_id(youtube_url)
            if video_id:
                playlist_add_queue.put(video_id)
                return jsonify({"message": f"Queued YouTube video: {video_id}"}), 200
            else:
                return jsonify({"message": "Could not extract video ID"}), 400
        else:
            return jsonify({"message": "No YouTube URL found"}), 400

    return jsonify({"message": "No matching feature for test event"}), 400

def get_obs_connection():
    ws = obsws(OBS_Host, OBS_Port, OBS_Password)
    ws.connect()
    return ws

def fade_filter(ws, source, filter_name, start, end, duration=3.0, steps=60):
    step_time = duration / steps
    for i in range(steps + 1):
        value = start + (end - start) * (i / steps)
        ws.call(obs_requests.SetSourceFilterSettings(
            sourceName=source,
            filterName=filter_name,
            filterSettings={"opacity": value}
        ))
        time.sleep(step_time)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port="5000", debug=True, use_reloader=False)