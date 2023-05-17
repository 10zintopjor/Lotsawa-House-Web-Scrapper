from pathlib import Path
import json
import os

def read_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data


def get_files(data):
    ids = data["ids"]
    counter=1
    for pair in ids:
        formatted_id = str(counter).zfill(5)
        prefix = f"./views/TM{formatted_id}"
        os.makedirs(prefix)
        for lang,text_file in pair:
            text = Path(f"./data/{text_file}").read_text(encoding="utf-8")
            view_path = f"{prefix}/{lang}.txt"
            Path(view_path).touch()
            Path(view_path).write_text(text,encoding="utf-8")
        counter+=1


if __name__ == "__main__":
    json_path = "data.json"
    data = read_json(json_path)
    get_files(data)



