import requests

event = {
    "type": "TLAPBOT_REDEEM_NOTE_SUCCESS",
    "eventData": {
        "redeem": "bounce",
        "note": "https://i.redd.it/vo9vm1fcqrp71.jpg"
    }
}

resp = requests.post("http://localhost:5000/test_event", json=event)
print(resp.status_code, resp.text)