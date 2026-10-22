"""Shared bits for the chris-mods apps: where things live on the Mac, and writing a page.

Each app is one HTML file you open in a browser. The ones that need your data have a build.py that reads
labeau-ops (and, for the line bank, the vault's Packets folder) and writes the page into
~/Developer/claude-mods/apps-out/, which git never sees. Nothing here sends anything anywhere.
"""
import csv, json, os, re

HOME = os.path.expanduser("~")
MODS = os.path.join(HOME, "Developer", "claude-mods")
OPS = os.environ.get("LABEAU_OPS", os.path.join(HOME, "Developer", "labeau-ops"))
OUT = os.environ.get("APPS_OUT", os.path.join(MODS, "apps-out"))
HERE = os.path.dirname(os.path.abspath(__file__))


def ops_config(key):
    """One top-level string from labeau-ops/config.yaml, without needing PyYAML."""
    if key == "vault" and os.environ.get("LABEAU_VAULT"):
        return os.environ["LABEAU_VAULT"]
    try:
        text = open(os.path.join(OPS, "config.yaml"), encoding="utf-8").read()
    except OSError:
        return ""
    m = re.search(r'^%s:\s*"?([^"\n#]*)"?' % re.escape(key), text, re.M)
    return m.group(1).strip() if m else ""


def read_csv(name):
    path = os.path.join(OPS, "data", name)
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_page(app, data, out_name=None):
    """Fill the app's page.html with data (as JSON) and write it to apps-out."""
    template = open(os.path.join(HERE, app, "page.html"), encoding="utf-8").read()
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, out_name or f"{app}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(template.replace("/*DATA*/null", blob))
    return path
