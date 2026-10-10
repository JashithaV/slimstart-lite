import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp")
import json
import hashlib
import numpy as np
import pandas as pd
import requests
from PIL import Image
import matplotlib.pyplot as plt


def handler(event, context=None):
    action = event.get("action", "hash")

    if action == "hash":
        h = b"x"
        for _ in range(2000):
            h = hashlib.sha256(h).digest()
        return {"statusCode": 200, "body": h.hex()[:16]}

    if action == "stats":
        a = np.random.rand(500, 500)
        return {"statusCode": 200, "body": json.dumps({"det": float(np.linalg.det(a))})}

    if action == "report":
        df = pd.DataFrame({"g": list("abab"), "v": [1, 2, 3, 4]})
        return {"statusCode": 200, "body": df.groupby("g").v.sum().to_json()}

    if action == "image":
        img = Image.new("RGB", (800, 800)).resize((200, 200))
        return {"statusCode": 200, "body": str(img.size)}

    if action == "http":  # builds a request without using the network
        url = requests.Request("GET", "https://example.com", params={"q": 1}).prepare().url
        return {"statusCode": 200, "body": url}

    if action == "plot":
        fig = plt.figure()
        plt.plot([1, 2, 3])
        plt.close(fig)
        return {"statusCode": 200, "body": "plotted"}

    return {"statusCode": 400, "body": "unknown action"}