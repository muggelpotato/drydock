import io
import json
import os
import subprocess
import sys
import tempfile
import time
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
BUILD = ROOT / "build"
PRODUCTS = {"modpack": "*.mrpack", "resourcepack": "drydock.zip"}


def run(*args):
    return subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()

def versions(toml):
    config = tomllib.loads(toml)
    return {part: config[part]["version"] for part in PRODUCTS}

def files(source):
    with zipfile.ZipFile(source) as archive:
        found = {name: archive.read(name) for name in archive.namelist() if not name.endswith("/")}
    for name, data in found.items():
        if name.endswith(".zip"):
            found[name] = files(io.BytesIO(data))
        elif name == "modrinth.index.json":
            found[name] = json.loads(data) | {"versionId": None}
    return found

def products(folder):
    return {part: files(next(folder.glob(pattern))) for part, pattern in PRODUCTS.items()}


new = versions((ROOT / "drydock.toml").read_text("utf-8"))
last = run("gh", "release", "list", "--limit", "1", "--exclude-drafts", "--json", "tagName", "--jq", ".[].tagName")
if last:
    old = versions(run("git", "show", f"{last}:drydock.toml"))
    with tempfile.TemporaryDirectory() as folder:
        run("gh", "release", "download", last, "--dir", folder)
        before = products(Path(folder))
    after = products(BUILD)
    changed = {part: sorted(name for name in before[part].keys() | after[part].keys() if before[part].get(name) != after[part].get(name)) for part in PRODUCTS}
    errors = [f"{part} changed since {last} but is still {new[part]}: {', '.join(changed[part][:3])}" for part in PRODUCTS if changed[part] and new[part] == old[part]]
    errors += [f"{part} is {new[part]} now but didn't change since {last}" for part in PRODUCTS if not changed[part] and new[part] != old[part]]
    if not any(changed.values()):
        errors.append(f"nothing changed since {last}")
    if errors:
        sys.exit("\n".join(errors))

day = time.strftime("%Y-%m-%d", time.gmtime())
earlier = len(run("git", "tag", "--list", f"{day}*").split())
tag = f"{day}.{earlier + 1}" if earlier else day
title = ", ".join(f"{part.capitalize()} {new[part]}" for part in PRODUCTS)
subprocess.run(["gh", "release", "create", tag, *BUILD.iterdir(), "--target", os.environ["GITHUB_SHA"], "--title", title], cwd=ROOT, check=True)