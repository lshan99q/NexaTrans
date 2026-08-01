import json, urllib.request

TOKEN = "YOUR_GITHUB_TOKEN"
REPO = "lshan99q/NexaTrans"

releases = {
    "v0.5": {
        "name": "v0.5 - Stage 5: OCR Text Recognition",
        "body": "## Stage 5: OCR Recognition\n\n- PP-OCRv5 ONNX recognition engine\n- Inline OCR with MD5 cache (64 entries)\n- CLAHE image preprocessing for better accuracy\n- OCR text overlay on detection boxes (white text)\n- OCR toggle from UI\n- Green box show/hide toggle independently\n- Clean capture mode (hides overlay for detection)",
        "prerelease": True
    },
    "v1.0": {
        "name": "v1.0 - Complete AI Translation Pipeline",
        "body": "## v1.0 - Complete AI Translation\n\n### New Features\n- One-click translation: detection + OCR + DeepSeek AI\n- Redesigned dark-themed UI with expandable settings panel\n- DeepSeek Chat API integration (urllib, zero extra deps)\n- Multi-region parallel translation (ThreadPoolExecutor)\n- Persistent translation cache (MD5 + JSON file)\n- Click-through overlay (Win32 WS_EX_TRANSPARENT)\n- All UI settings persisted across sessions\n- API connectivity test button in settings\n- Red border toggle for region verification\n- Console-free mode (use main.pyw)\n- Chinese UI\n\n### Pipeline\nScreen -> DBNet++ -> Mask -> PP-OCRv5 -> DeepSeek -> Overlay",
        "prerelease": False
    },
    "v1.1": {
        "name": "v1.1 - System Tray and Polish",
        "body": "## v1.1 - System Tray\n\n- System tray icon with context menu\n- Minimize to tray on close (X button hides to tray)\n- Tray menu: open window, start/stop translation, quit\n- Live status in tray (FPS, box count, static/dynamic)\n- Double-click tray icon to restore window\n- Background translation while minimized\n- All settings persist across sessions\n- Clean README\n- Version bump to v1.1",
        "prerelease": False
    },
}

def req(method, url, data=None):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "NexaTrans",
    }
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(r) as resp:
        return json.loads(resp.read())

for tag, info in releases.items():
    payload = {
        "tag_name": tag,
        "name": info["name"],
        "body": info["body"],
        "draft": False,
        "prerelease": info["prerelease"],
    }
    try:
        result = req("POST", f"https://api.github.com/repos/{REPO}/releases", payload)
        print(f"Created: {tag} -> {result['html_url']}")
    except urllib.error.HTTPError as e:
        if e.code == 422:
            # Release exists, update it
            try:
                existing = req("GET", f"https://api.github.com/repos/{REPO}/releases/tags/{tag}")
                update_payload = {
                    "tag_name": tag,
                    "name": info["name"],
                    "body": info["body"],
                    "draft": False,
                    "prerelease": info["prerelease"],
                }
                result = req("PATCH", f"https://api.github.com/repos/{REPO}/releases/{existing['id']}", update_payload)
                print(f"Updated: {tag} -> {result['html_url']}")
            except Exception as e2:
                print(f"Update failed for {tag}: {e2}")
        else:
            print(f"Failed for {tag}: HTTP {e.code} - {e.read().decode()}")
    except Exception as e:
        print(f"Failed for {tag}: {e}")

print("Done")
