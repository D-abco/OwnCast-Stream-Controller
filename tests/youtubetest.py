import requests

# Test event for adding a YouTube video via the /test_event endpoint
event = {
    "type": "TLAPBOT_REDEEM_NOTE_SUCCESS",
    "eventData": {
        "redeem": "play",
        "custom_message": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    }
}

resp = requests.post("http://localhost:5000/test_event", json=event)
print("Status:", resp.status_code)
print("Response:", resp.text)