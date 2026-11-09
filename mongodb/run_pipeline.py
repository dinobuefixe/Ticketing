

import argparse
import json
import os
from pathlib import Path

from bson import json_util
from pymongo import MongoClient

PIPELINES = Path(__file__).parent / "pipelines"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=int, help="número do relatório (1 a 6)")
    parser.add_argument("--limit", type=int, default=5, help="máximo de documentos a mostrar")
    args = parser.parse_args()

    spec = json.loads((PIPELINES / f"report{args.report}.json").read_text(encoding="utf-8"))
    db = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=5000).get_default_database()

    pipeline = spec["pipeline"] + [{"$limit": args.limit}]
    for doc in db[spec["collection"]].aggregate(pipeline, allowDiskUse=True):
        print(json_util.dumps(doc, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()