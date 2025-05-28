from obswebsocket import obsws, requests as obs_requests
import time
from threading import Thread
import queue
import os
import json

superchat_queue = queue.Queue()

with open(os.path.join(os.path.dirname(__file__), '..', 'config.json'), 'r') as f:
    config = json.load(f)

SUPERCHAT_POPUP_SOURCE = config.get("SUPERCHAT_POPUP_SOURCE")
SUPERCHAT_TEXT_INPUT = config.get("SUPERCHAT_TEXT_INPUT")
SUPERCHAT_USER_INPUT = config.get("SUPERCHAT_USER_INPUT")

def start_superchat_worker(obs_host, obs_port, obs_password):
    def superchat_worker():
        ws = obsws(obs_host, obs_port, obs_password)
        ws.connect()
        print("Connected to OBS from Superchat worker")

        while True:
            display_name, message = superchat_queue.get()
            print(f"Displaying superchat from {display_name}: {message}")

            try:
                ws.call(obs_requests.SetSourceFilterSettings(
                    sourceName=SUPERCHAT_POPUP_SOURCE,
                    filterName="FadeIn",
                    filterSettings={"opacity": 1.0}
                ))
                ws.call(obs_requests.SetInputSettings(
                    inputName=SUPERCHAT_TEXT_INPUT,
                    inputSettings={"text": message},
                    overlay=True
                ))
                ws.call(obs_requests.SetInputSettings(
                    inputName=SUPERCHAT_USER_INPUT,
                    inputSettings={"text": display_name},
                    overlay=True
                ))
                print("Displayed message in OBS.")

                ws.call(obs_requests.TriggerHotkeyByName(hotkeyName="play_superchat_audio_hotkey"))
                print("Triggered Lua hotkey for Superchat audio.")

                
                fade_filter(ws, SUPERCHAT_POPUP_SOURCE, "FadeIn", 0.0, 1.0, duration=3.0, steps=60)
                time.sleep(3)
                fade_filter(ws, SUPERCHAT_POPUP_SOURCE, "FadeIn", 1.0, 0.0, duration=3.0, steps=60)
                time.sleep(1)

                ws.call(obs_requests.SetInputSettings(
                    inputName=SUPERCHAT_TEXT_INPUT,
                    inputSettings={"text": ""},
                    overlay=True
                ))
                ws.call(obs_requests.SetInputSettings(
                    inputName=SUPERCHAT_USER_INPUT,
                    inputSettings={"text": ""},
                    overlay=True
                ))
                print("Cleared message from OBS.")

            except Exception as e:
                print("OBS Error:", e)

            superchat_queue.task_done()

        ws.disconnect()

    Thread(target=superchat_worker, daemon=True).start()

def fade_filter(ws, source, filter_name, start, end, duration=3.0, steps=60):
    import time
    step_time = duration / steps
    for i in range(steps + 1):
        value = start + (end - start) * (i / steps)
        ws.call(obs_requests.SetSourceFilterSettings(
            sourceName=source,
            filterName=filter_name,
            filterSettings={"opacity": value}
        ))
        time.sleep(step_time)