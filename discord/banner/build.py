# render.py + boat.glb -> frboatspin.webp, frboatspin-ingame.webp, boatspin.webp, boatspin.jxl
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
TEMP = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
FRAMES = Path(TEMP.name)
FPS = 30
DISCORD = 900, 300
blender = shutil.which("blender") or max(Path("C:/Program Files/Blender Foundation").glob("*/blender.exe"))


def render(lighting):
    subprocess.run([blender, "-b", "--factory-startup", "-P", HERE / "render.py", "--", FRAMES / lighting, str(FPS), lighting], check=True)
    return [Image.open(path) for path in sorted((FRAMES / lighting).glob("*.png"))]

def save(frames, name):
    frames[0].save(HERE / name, save_all=True, append_images=frames[1:], duration=1000 / FPS, quality=95, method=4)


studio = render("studio")
save(studio, "frboatspin.webp")
save(render("ingame"), "frboatspin-ingame.webp")
small = [frame.resize(DISCORD, Image.LANCZOS) for frame in studio]
save(small, "boatspin.webp")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", "%dx%d" % DISCORD, "-framerate", str(FPS), "-i", "-", "-c:v", "libjxl_anim", "-f", "image2pipe", HERE / "boatspin.jxl"], input=b"".join(frame.tobytes() for frame in small), check=True)