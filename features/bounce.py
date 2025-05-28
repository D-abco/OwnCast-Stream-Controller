import queue
from threading import Thread
import time
import os
from PIL import Image
import requests as pyrequests
from obswebsocket import obsws, requests as obs_requests
import uuid
import json

bounce_queue = queue.Queue()

with open(os.path.join(os.path.dirname(__file__), '..', 'config.json'), 'r') as f:
    config = json.load(f)

SCENE_NAME = config.get("SCENE_NAME")
BOUNCE_SOURCE_NAME = config.get("BOUNCE_SOURCE_NAME")

def resize(image_url):
    response = pyrequests.get(image_url, stream=True)
    response.raise_for_status()
    img = Image.open(response.raw).convert("RGBA")
    img.thumbnail((200, 200), Image.LANCZOS)
    bg = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    bg.paste(img, ((200 - img.width) // 2, (200 - img.height) // 2))
    filename = f"{uuid.uuid4().hex}.png"
    save_dir = os.path.join(os.path.dirname(__file__), "..", "static", "bounce")
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.abspath(os.path.join(save_dir, filename))
    bg.save(save_path, format="PNG")
    url = f"http://localhost:5000/static/bounce/{filename}"
    return url, save_path  # Return both



def start_bounce_worker(obs_host, obs_port, obs_password):
    def bounce_worker():
        ws = obsws(obs_host, obs_port, obs_password)
        ws.connect()
        print("Connected to OBS for bounce events")
        while True:
            image_url = bounce_queue.get()
            try:
                bounce_url, local_path = resize(image_url)
                ws.call(obs_requests.SetInputSettings(
                    inputName=BOUNCE_SOURCE_NAME,
                    inputSettings={"file": bounce_url},
                    overlay=True
                ))
                scene_name = SCENE_NAME
                item_name = BOUNCE_SOURCE_NAME
                response = ws.call(obs_requests.GetSceneItemList(sceneName=scene_name))
                print("OBS response object:", response)
                print("OBS response dir:", dir(response))
                print("OBS response datain:", getattr(response, 'datain', None))
                print("OBS response data:", getattr(response, 'data', None))
                if hasattr(response, 'status') and not response.status:
                    print(f"OBS returned error for scene '{scene_name}'. Check if the scene exists and OBS WebSocket is working.")
                    continue
                scene_items = None
                if hasattr(response, 'datain'):
                    scene_items = response.datain.get('sceneItems')
                elif hasattr(response, 'getDatain'):
                    scene_items = response.getDatain().get('sceneItems')
                elif hasattr(response, 'getSceneItems'):
                    scene_items = response.getSceneItems()
                if scene_items is None:
                    print("Bounce worker error: 'sceneItems' not found in OBS response!")
                    continue
                bounce_item_id = None
                for item in scene_items:
                    if item['sourceName'] == BOUNCE_SOURCE_NAME:
                        bounce_item_id = item['sceneItemId']
                        break
                if bounce_item_id is not None:
                    ws.call(obs_requests.SetSceneItemTransform(
                        sceneName=scene_name,
                        sceneItemId=bounce_item_id,
                        sceneItemTransform={
                            "scaleX": 1.0,
                            "scaleY": 1.0,
                            "positionX": 1600,
                            "positionY": 800
                        }
                    ))
                    print("Bounce image set to 100x100 via Pillow.")
                else:
                    print("Bounce scene item not found!")
                ws.call(obs_requests.SetSourceFilterSettings(
                    sourceName=BOUNCE_SOURCE_NAME,
                    filterName="FadeIn",
                    filterSettings={"opacity": 1}
                ))
                print("Bounce image set and opacity 100.")
                ws.call(obs_requests.TriggerHotkeyByName(hotkeyName="toggle_bounce"))
                print("Bounce Lua script toggled.")
                time.sleep(30)
                ws.call(obs_requests.SetSourceFilterSettings(
                    sourceName=BOUNCE_SOURCE_NAME,
                    filterName="FadeIn",
                    filterSettings={"opacity": 0.0}
                ))
                print("Bounce opacity set to 0.")
                ws.call(obs_requests.TriggerHotkeyByName(hotkeyName="toggle_bounce"))
                print("Bounce Lua script toggled again.")
                os.unlink(local_path)
            except Exception as e:
                print("Bounce worker error:", e)
            bounce_queue.task_done()
        ws.disconnect()
    Thread(target=bounce_worker, daemon=True).start()