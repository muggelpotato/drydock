import os
import sys
import subprocess
import webbrowser
import difflib
import re

sys.stdout.reconfigure(errors='replace')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)

STATE_FILE = os.path.join(SCRIPT_DIR, ".fo-last-commit")
IGNORE_FILE = os.path.join(SCRIPT_DIR, ".compare-ignore")
REMOTE = "fo-upstream"

def run_git(args, check=True):
    r = subprocess.run(["git"] + args, capture_output=True, text=True, encoding="utf-8", cwd=ROOT_DIR)
    if check and r.returncode != 0:
        print(f"Git error: {r.stderr}", file=sys.stderr)
        sys.exit(r.returncode)
    return r.stdout.strip()

def generate_html_report(last, latest, pathspecs):
    files = [f.strip() for f in run_git(["diff", "--name-only", last, latest, "--"] + pathspecs).splitlines() if f.strip()]
    if not files: return False
    
    html_tables = []
    for f in files:
        old = [l for l in run_git(["show", f"{last}:{f}"], check=False).splitlines() if not any(x in l for x in ["hash =", "url =", "hash-format ="])]
        new = [l for l in run_git(["show", f"{latest}:{f}"], check=False).splitlines() if not any(x in l for x in ["hash =", "url =", "hash-format ="])]
        
        if old == new:
            continue
            
        table = difflib.HtmlDiff().make_table(old, new, fromdesc=f"{last[:10]}/{f}", todesc=f"{latest[:10]}/{f}", context=True, numlines=3)
        table = re.sub(
            r'(?:\s*<colgroup>\s*</colgroup>)+',
            '<colgroup><col style="width: 50px;"><col style="width: calc(50% - 50px);"><col style="width: 50px;"><col style="width: calc(50% - 50px);"></colgroup>',
            table
        )
        html_tables.append(f"<h2>{f}</h2>\n{table}")

    if not html_tables:
        return False

    css = """
    body { font-family: sans-serif; padding: 20px; background: #1e1e1e; color: #d4d4d4; }
    h1 { color: #569cd6; border-bottom: 2px solid #3c3c3c; padding-bottom: 10px; }
    h2 { color: #4ec9b0; margin-top: 40px; border-bottom: 1px solid #3c3c3c; padding-bottom: 5px; font-size: 18px; }
    table.diff { border-collapse: collapse; width: 100%; font-family: monospace; font-size: 12px; margin-bottom: 20px; border: 1px solid #3c3c3c; table-layout: fixed; }
    table.diff td { padding: 2px 6px; overflow: hidden; text-overflow: ellipsis; white-space: pre-wrap; word-wrap: break-word; }
    .diff_next, th.diff_next, td.diff_next { display: none !important; }
    td.diff_header { background: #2d2d2d; color: #858585; text-align: right; user-select: none; border-right: 1px solid #3c3c3c; }
    .diff_add { background: #264f2c; } .diff_chg { background: #5b4a24; } .diff_sub { background: #5c2429; }
    th { background: #333; color: #9cdcfe; font-weight: bold; text-align: left; padding: 6px; border-bottom: 1px solid #3c3c3c; }
    """
    
    report_file = os.path.join(ROOT_DIR, "upstream_diff.html")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>Upstream Diff</title><style>{css}</style></head><body><h1>Upstream Diff Report (Hash & URL filtered)</h1><p>Comparing <strong>{last[:10]}</strong> to <strong>{latest[:10]}</strong></p>{'<hr>'.join(html_tables)}</body></html>")
        
    print(f"Report saved to: {report_file}")
    webbrowser.open(os.path.abspath(report_file))
    return True

print("Fetching latest commits from upstream...")
run_git(["fetch", REMOTE])
latest = run_git(["rev-parse", f"{REMOTE}/main"])

pack_toml = os.path.join(ROOT_DIR, "pack", "pack.toml")
mc_version = None
if os.path.exists(pack_toml):
    with open(pack_toml, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("minecraft"):
                mc_version = line.split("=")[-1].strip().strip('"').strip("'")
                break

if not mc_version:
    print("Error: Could not read minecraft version from pack/pack.toml!", file=sys.stderr)
    sys.exit(1)

last = latest
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        last = f.read().strip()
else:
    last = run_git(["rev-parse", f"{REMOTE}/main~5"])
    with open(STATE_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write(last)

if "--ack" in sys.argv or "--update" in sys.argv:
    with open(STATE_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write(latest)
    print(f"Tracked commit updated to: {latest}")
    sys.exit(0)

if last == latest:
    print(f"\nModpack is up to date with upstream at commit {last}.")
    sys.exit(0)

pathspecs = [f"Packwiz/{mc_version}"]
if os.path.exists(IGNORE_FILE):
    with open(IGNORE_FILE, "r", encoding="utf-8") as f:
        pathspecs += [f":(exclude)**/{l.strip()}" for l in f if l.strip() and not l.startswith("#")]

if generate_html_report(last, latest, pathspecs):
    print(f"\nTo mark these changes as reviewed, run: python {os.path.relpath(__file__, os.getcwd())} --ack")
else:
    print(f"\nNo meaningful changes found between {last[:10]} and {latest[:10]} (only hashes/urls might have changed).")
    print(f"To mark as reviewed, run: python {os.path.relpath(__file__, os.getcwd())} --ack")
