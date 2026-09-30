import os

# Keep pytest on demo fixtures even when the local .env is APP_MODE=live.
os.environ["APP_MODE"] = "demo"
os.environ["FIRMS_MAP_KEY"] = ""
os.environ["OVERPASS_URL"] = "http://127.0.0.1:9/overpass-disabled"
