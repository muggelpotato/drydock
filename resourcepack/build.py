# pack.mcmeta + assets/ + icon.png + LICENSE -> build/drydock.zip
import json
import sys
import tomllib
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
cfg = tomllib.loads((ROOT / "drydock.toml").read_text("utf-8"))["resourcepack"]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "drydock.zip"

pack = {"pack_format": cfg["min_format"], "min_format": cfg["min_format"], "max_format": cfg["max_format"], "description": cfg["description"]}
(HERE / "pack.mcmeta").write_bytes(json.dumps({"pack": pack}, indent=4, ensure_ascii=False).encode())

files = {"pack.mcmeta": HERE / "pack.mcmeta", "pack.png": ROOT / "icon.png", "LICENSE": ROOT / "LICENSE"}
files |= {path.relative_to(HERE).as_posix(): path for path in sorted((HERE / "assets").rglob("*")) if path.is_file()}

OUT.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as archive:
    for name, path in files.items():
        archive.write(path, name)