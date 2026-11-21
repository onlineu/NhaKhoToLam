"""Name suggestions as you type, using a Trie (prefix tree) over the words of every item name."""
import re
import time

import db

CACHE_SECONDS = 30
MAX_CANDIDATES = 500
_END = object()           # marks "names end here"; cannot clash with a character
_cache = {"at": 0.0, "trie": None}


def _words(name):
    return [w for w in re.split(r"[\s-]+", name.casefold()) if w]


def build(names):
    """Trie: each node is a dict of character -> child. Time O(total characters), space O(total characters)."""
    root = {}
    for name in set(names):
        for word in set(_words(name)):
            node = root
            for ch in word:
                node = node.setdefault(ch, {})
            node.setdefault(_END, set()).add(name)
    return root


def _collect(node, found):
    """Depth-first walk of everything below a node."""
    stack = [node]
    while stack and len(found) < MAX_CANDIDATES:
        cur = stack.pop()
        for key, child in cur.items():
            if key is _END:
                found.update(child)
            else:
                stack.append(child)


def lookup(trie, terms, limit=8):
    """Names where every typed word starts some word of the name. Walks the Trie with the longest typed word."""
    seed = max(terms, key=len)
    node = trie
    for ch in seed:
        node = node.get(ch)
        if node is None:
            return []
    found = set()
    _collect(node, found)
    hits = [n for n in found if all(any(w.startswith(t) for w in _words(n)) for t in terms)]
    return sorted(hits, key=str.casefold)[:limit]


def invalidate():
    _cache["at"] = 0.0


def suggestions(terms, limit=8):
    """The Trie is cached for a few seconds in the warm Lambda, so each keystroke does not rescan the table."""
    if _cache["trie"] is None or time.time() - _cache["at"] > CACHE_SECONDS:
        _cache["trie"], _cache["at"] = build(db.scan_names()), time.time()
    return lookup(_cache["trie"], terms, limit)