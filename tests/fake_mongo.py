# tests/fake_mongo.py
import re
from datetime import datetime

class FakeCursor:
    def __init__(self, docs):
        self._docs = docs
        self._sort = None
        self._limit = None

    def sort(self, field, direction):
        reverse = direction == -1
        def getter(d):
            return _get_by_dotted(d, field)
        self._docs.sort(key=lambda d: getter(d), reverse=reverse)
        return self

    def limit(self, n):
        self._limit = n
        return self

    async def to_list(self, length):
        docs = self._docs[: self._limit or length]
        return docs

class FakeCollection:
    def __init__(self):
        self._docs = []

    def extend(self, docs):
        self._docs.extend(docs)

    async def distinct(self, field):
        vals = set()
        for d in self._docs:
            v = _get_by_dotted(d, field)
            vals.add(v)
        return list(vals)

    async def count_documents(self, query):
        return len(_filter_docs(self._docs, query))

    def find(self, query, projection=None):
        filtered = _filter_docs(self._docs, query)
        # projection is ignored (not needed for tests)
        return FakeCursor(filtered)

def _get_by_dotted(doc, dotted):
    cur = doc
    for part in dotted.split("."):
        if cur is None:
            return None
        cur = cur.get(part) if isinstance(cur, dict) else None
    return cur

def _matches_regex(value, regex, options=None):
    if value is None:
        return False
    flags = re.I if (options and "i" in options) else 0
    return re.search(regex, str(value), flags) is not None

def _compare(op, value, comp):
    try:
        # try datetime compare first
        if isinstance(value, datetime) or isinstance(comp, datetime):
            return (value >= comp) if op == "$gte" else (value <= comp)
        # else numeric if possible
        v1 = float(value)
        v2 = float(comp)
        return (v1 >= v2) if op == "$gte" else (v1 <= v2)
    except Exception:
        # fallback to string lexicographic
        v1 = str(value)
        v2 = str(comp)
        return (v1 >= v2) if op == "$gte" else (v1 <= v2)

def _match_field(value, cond):
    if isinstance(cond, dict):
        for k, v in cond.items():
            if k == "$regex":
                if not _matches_regex(value, v, cond.get("$options")):
                    return False
            elif k in ("$gte", "$lte"):
                if not _compare(k, value, v):
                    return False
            else:
                # unsupported operator -> fail strict
                return False
        return True
    else:
        return value == cond

def _filter_docs(docs, query):
    def match(doc, q):
        for k, cond in q.items():
            v = _get_by_dotted(doc, k)
            if not _match_field(v, cond):
                return False
        return True
    return [d for d in docs if match(d, query)]

class FakeDB:
    def __init__(self):
        self.collections = {"metar_data": []}
    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = []
        # Return a collection-like wrapper
        fc = FakeCollection()
        # bind to the same list
        fc._docs = self.collections[name]
        return fc

class FakeMongoClient:
    pass
