from openpecha import github_utils,config
import os
import csv
from pathlib import Path
from github import RateLimitExceededException,GithubException
from datetime import datetime
import time


def publish_repo(pecha_path, asset_paths=None):
    print(f"PECHA_PATH {pecha_path}")
    try:
        github_utils.github_publish(
            pecha_path,
            message="initial commit",
            not_includes=[],
            layers=[],
            org=os.environ.get("OPENPECHA_DATA_GITHUB_ORG"),
            token=os.environ.get("GITHUB_TOKEN")
        )
    except GithubException as e:
        if e.status == 403 and 'rate limit' in e.data.get('message', ''):
            reset_time = int(e.headers.get('x-ratelimit-reset', 0))
            current_time = int(time.time())
            wait_time = max(reset_time - current_time, 0) + 10
            print(f"Rate limit exceeded. Waiting for {wait_time} seconds before retrying...")
            time.sleep(wait_time)
        else:
            print("Error occurred:", str(e))

def publish():
    bool_try = True
    with open("data/logs_v1/pechas_catalog.csv","r") as f1:
        obj = csv.reader(f1)
        for row in obj:
            id = row[0]
            if bool_try:
                pecha_path = Path(f"./data/zot_dir_v1/opfs/{id}")
                publish_repo(pecha_path=pecha_path)
                print(id)
                time.sleep(3)
            if id == "A470FDB37":
                bool_try =True
            

if __name__ == "__main__":
    publish()