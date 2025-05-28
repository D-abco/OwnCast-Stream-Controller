# SongRequest

A Flask-based web application for managing YouTube song requests, superchats, and interactive OBS overlays for live streams.  
Integrates with OBS via obs-websocket, YouTube Data API, and supports custom features like DVD Bouncing images, Superchat popups, and Challenge (Brainrot in this case) events.

---

## Features

- **YouTube Playlist Management:**  
  Add, skip, and clear songs in a YouTube playlist via web interface or chat commands.
- **OBS Integration:**  
  Control scenes, sources, and overlays in OBS using obs-websocket.
- **Superchat Popups:**  
  Display superchat messages and usernames on stream.
- **Bounce Images:**  
  Show and animate images on stream in response to events. Kinda like the DVD logo
- **Challenge Events:**  
  Display custom text and challenges on stream.
- **Test Event Endpoints:**  
  Easily trigger and debug features via HTTP endpoints.

---

## Requirements

- Python 3.8+
- OBS Studio (with obs-websocket plugin, v4.x for this codebase)
- Google Cloud Project with YouTube Data API enabled
- A YouTube playlist to manage
- [pip](https://pip.pypa.io/en/stable/)

---

## Setup

### 1. Clone the Repository

```sh
git clone https://github.com/yourusername/SongRequest.git
cd SongRequest
```

### 2. Create and Activate a Virtual Environment

```sh
python3 -m venv songrequest-venv
source songrequest-venv/bin/activate
```

### 3. Install Dependencies

```sh
pip install -r requirements.txt
```

### 4. Configure OBS

- Install [obs-websocket](https://github.com/obsproject/obs-websocket) plugin for OBS (v4.x).
- Set the OBS WebSocket server address, port, and password.

### 4a. Optional

I use a few lua scripts from obsproject.com to create some animated functions.

- https://obsproject.com/forum/resources/bounce.947/ 
-# jbscript

I cannot find the other one I use but it toggles a timer to start, the one I use is created by a user named Lain

### 5. Configure Google API

- Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
- Create OAuth 2.0 credentials for a Web Application.
- Copy your **Client ID** and **Client Secret**.

### 6. Configure the App

- Copy `configexample.json` to `config.json`:
  ```sh
  cp configexample.json config.json
  ```
- Fill in all required fields in `config.json`:
  - OBS connection info
  - Google OAuth credentials
  - Playlist ID
  - Scene and source names as used in your OBS setup

### 7. Run the App

```sh
python app.py
```

- Visit [http://localhost:5000](http://localhost:5000) in your browser.
- On first use, you will be prompted to authorize with Google. This will generate `token.json`.


---

## File Structure

```
SongRequest/
├── app.py
├── config.json
├── configexample.json
├── requirements.txt
├── features/
│   ├── bounce.py
│   ├── brainrot.py
│   ├── superchat.py
│   └── youtube.py
├── static/
│   └── bounce/
├── templates/
│   └── index.html
├── tests/
│   └── (test scripts)
├── .gitignore
└── README.md
```

---

## Customization

- **Scene and Source Names:**  
  Set these in `config.json` to match your OBS setup.
- **Filter Names:**  
  These are hardcoded in the Python files. Change them if your OBS filters use different names. The filter name I use is FadeIn.

---

## Troubleshooting

- **OBS Connection Issues:**  
  Ensure obs-websocket is installed and running, and the host/port/password in `config.json` are correct.
- **YouTube API Errors:**  
  Make sure your Google project has the YouTube Data API enabled and your OAuth credentials are correct.
- **No `token.json`:**  
  Complete the OAuth flow in your browser to generate this file.


---

## Credits

- [obs-websocket-py](https://github.com/Elektordi/obs-websocket-py)
- [Flask](https://flask.palletsprojects.com/)
- [Google API Python Client](https://github.com/googleapis/google-api-python-client)