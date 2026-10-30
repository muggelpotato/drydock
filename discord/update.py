import json
import sys
import tomllib
import urllib.error
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).parent
ENV = HERE / ".env"
pairs = (line.split("=", 1) for line in ENV.read_text("utf-8").splitlines() if "=" in line and not line.startswith("#"))
env = {key.strip(): value.strip().strip("'\"") for key, value in pairs}
message_id = env.get("DISCORD_MESSAGE_ID")
minecraft = tomllib.loads((HERE.parent / "drydock.toml").read_text("utf-8"))["minecraft"]
message = (HERE / "message.json").read_text("utf-8").replace("{minecraft}", minecraft)


boundary = uuid.uuid4().hex
fields = [('name="payload_json"', message.encode())] + [(f'name="files[{file["id"]}]"; filename="{file["filename"]}"', (HERE / "banner" / file["filename"]).read_bytes()) for file in json.loads(message)["attachments"]]
body = b"".join(f"--{boundary}\r\nContent-Disposition: form-data; {field}\r\n\r\n".encode() + data + b"\r\n" for field, data in fields) + f"--{boundary}--\r\n".encode()

path = f"/messages/{message_id}" if message_id else ""
url = env["DISCORD_WEBHOOK_URL"].rstrip("/") + path + "?wait=true&with_components=true"
headers = {"Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": "DrydockDiscordUpdater/1.0"}
try:
    request = urllib.request.Request(url, body, headers, method="PATCH" if message_id else "POST")
    response = json.loads(urllib.request.urlopen(request, timeout=60).read())
except urllib.error.HTTPError as error:
    sys.exit(f"{error}: {error.read().decode()}")

if not message_id:
    lines = [line for line in ENV.read_text("utf-8").splitlines() if not line.startswith("DISCORD_MESSAGE_ID")]
    ENV.write_text("\n".join([*lines, f"DISCORD_MESSAGE_ID={response['id']}"]) + "\n", "utf-8")
print("Edited" if message_id else "Posted", "message", response["id"])