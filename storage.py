"""Saves every agent, match and generation summary.
Always writes JSON (runs/<run_id>.json). Also writes to MongoDB when MONGODB_URI
is set (pip install pymongo), which is what powers the family tree for the prize."""
import json
import os
import time
from pathlib import Path


class Store:
    def __init__(self, run_id):
        self.run_id = run_id
        self.data = {"run_id": run_id, "started": time.time(),
                     "agents": {}, "generations": [], "matches": []}
        self.db = None
        uri = os.getenv("MONGODB_URI")
        if uri:
            try:
                from pymongo import MongoClient
                self.db = MongoClient(uri)[os.getenv("MONGODB_DB", "agent_arena")]
                print("  MongoDB logging on")
            except Exception as e:
                print(f"  ! MongoDB off ({e})")

    def _mongo(self, coll, doc):
        if self.db is not None:
            self.db[coll].insert_one(doc | {"run_id": self.run_id})

    def agent(self, a):
        d = a.to_dict()
        self.data["agents"][a.id] = d
        self._mongo("agents", dict(d))

    def match(self, gen, p1, p2, result, moves, kind):
        d = {"generation": gen, "p1": p1, "p2": p2, "winner": result, "moves": moves, "kind": kind}
        self.data["matches"].append(d)
        self._mongo("matches", dict(d))

    def generation(self, summary):
        self.data["generations"].append(summary)
        self._mongo("generations", dict(summary))

    def save(self, folder="runs"):
        Path(folder).mkdir(exist_ok=True)
        path = Path(folder) / f"{self.run_id}.json"
        path.write_text(json.dumps(self.data, indent=1))
        (Path(folder) / "latest.json").write_text(json.dumps(self.data, indent=1))
        return path
