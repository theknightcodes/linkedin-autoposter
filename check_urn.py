import requests, os
from dotenv import load_dotenv
load_dotenv(".env")

token         = os.getenv("LINKEDIN_ACCESS_TOKEN")
client_id     = os.getenv("LINKEDIN_CLIENT_ID")
client_secret = os.getenv("LINKEDIN_CLIENT_SECRET")

r = requests.post(
    "https://www.linkedin.com/oauth/v2/introspectToken",
    data={
        "client_id":     client_id,
        "client_secret": client_secret,
        "token":         token,
    },
)
print(r.status_code)
import json; print(json.dumps(r.json(), indent=2))
