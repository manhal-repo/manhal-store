import json, os, hashlib

repo = os.environ["GITHUB_REPOSITORY"]
app_id = os.environ["APP_ID"]
app_name = os.environ["APP_NAME"]
version = os.environ["VERSION"]
p = "public/catalog/apps.json"

if os.path.exists(p):
    data = json.load(open(p, encoding="utf-8"))
else:
    data = {"apps": []}

app = next((a for a in data["apps"] if a["id"] == app_id), None)
if not app:
    app = {"id": app_id, "name": app_name, "summary": "",
           "description": "", "categories": ["Others"], "downloads": []}
    data["apps"].append(app)

for f in sorted(os.listdir("dl")):
    osn = "windows" if f.endswith(".exe") else "linux"
    b = open("dl/" + f, "rb").read()
    app["downloads"] = [d for d in app["downloads"] if d["os"] != osn]
    app["downloads"].append({
        "os": osn,
        "version": version,
        "size": len(b),
        "sha256": hashlib.sha256(b).hexdigest(),
        "url": f"https://github.com/{repo}/releases/download/files/{f}",
    })

os.makedirs(os.path.dirname(p), exist_ok=True)
json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("done")
