import time
import random
from threading import Thread
from obswebsocket import obsws, requests as obs_requests
import json
import os



GEN_Z_SLANG = [
    "rizz",
    "slay",
    "no cap",
    "bet",
    "sus",
    "drip",
    "mid",
    "bussin",
    "ratio",
    "gyatt",
    "skibidi",
    "goated",
    "yeet",
    "stan",
    "simp",
    "based",
    "bruh",
    "cap",
    "touch grass",
    "pookie"
]

MARIO64_CHALLENGES = {
    "no_jump": "Complete the next star without jumping.",
    "one_hand": "Play with only one hand for 2 minutes.",
    "invert_controls": "Invert your controller for 1 star.",
    "no_camera": "Don't touch the camera controls for 1 star.",
    "collect_coins": "Collect 50 coins before next star.",
    "no_damage": "Don't take damage for 1 star.",
    "backwards_only": "Move only backwards for 1 minute.",
    "no_cap": "No cap powerups for 1 star.",
    "crawl_only": "Crawl only for 30 seconds.",
    "no_long_jump": "No long jumps for 1 star.",
    "no_run": "Walk, don't run, for 1 star."
}


with open(os.path.join(os.path.dirname(__file__), '..', 'config.json'), 'r') as f:
    config = json.load(f)

BRAINROT_SOURCE_WORDS = config.get("BRAINROT_SOURCE_WORDS")
BRAINROT_SOURCE_CHALLENGE = config.get("BRAINROT_SOURCE_CHALLENGE")
BRAINROT_SOURCE_GROUP = config.get("BRAINROT_SOURCE_GROUP")

BRAINROT_COOLDOWN = 600  
brainrot_last_time = 0

def start_brainrot_worker(obs_host, obs_port, obs_password):

    def handle_brainrot_event():
        global brainrot_last_time
        now = time.time()
        if now - brainrot_last_time < BRAINROT_COOLDOWN:
            print("Brainrot redeem is on cooldown.")
            return
        brainrot_last_time = now

        # Pick 5 unique random slang words
        slang_words = random.sample(GEN_Z_SLANG, min(5, len(GEN_Z_SLANG)))
        slang_text = ", ".join(slang_words)
        challenge_key, challenge_desc = random.choice(list(MARIO64_CHALLENGES.items()))
        print(f"[BRAINROT] Slang: {slang_text}")
        print(f"[BRAINROT] Mario 64 Challenge: {challenge_desc}")

        ws = obsws(obs_host, obs_port, obs_password)
        ws.connect()
        try:
            ws.call(obs_requests.SetInputSettings(
                inputName=BRAINROT_SOURCE_WORDS,
                inputSettings={"text": slang_text},
                overlay=True
            ))
            ws.call(obs_requests.SetInputSettings(
                inputName=BRAINROT_SOURCE_CHALLENGE,
                inputSettings={"text": challenge_desc},
                overlay=True
            ))
            ws.call(obs_requests.SetSourceFilterSettings(
                sourceName=BRAINROT_SOURCE_GROUP,
                filterName="FadeIn",
                filterSettings={"opacity": 1.0}
            ))
            ws.call(obs_requests.TriggerHotkeyByName(hotkeyName="reset_timer_thingy"))

            def fade_out_skibidi():
                time.sleep(299)
                ws2 = obsws(obs_host, obs_port, obs_password)
                ws2.connect()
                ws2.call(obs_requests.SetSourceFilterSettings(
                    sourceName=BRAINROT_SOURCE_GROUP,
                    filterName="FadeIn",
                    filterSettings={"opacity": 0.0}
                ))
                ws2.disconnect()
            Thread(target=fade_out_skibidi, daemon=True).start()

        except Exception as e:
            print("Brainrot OBS error:", e)
        finally:
            ws.disconnect()

    return handle_brainrot_event