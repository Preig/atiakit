"""Find watched business names in an answer, and watched domains in its citations.

Rules:
  * Case-insensitive, whole words only: "Bay Light" matches "bay light's" but not
    "Bay Lightning" or "Baylight".
  * Every alias counts as the business. Overlapping hits (an alias inside the full
    name) count once.
  * Spaces between words may also be hyphens or line breaks. Curly apostrophes
    count as straight ones. A trailing period in a name ("Co.") is optional.
  * Cited = a watched domain appears in the answer's citation URLs. A domain entry
    may include a path ("ota.example/tours/bay-light") to count one listing page.
  * Google grounding redirect links are matched on their resolved URL, or, when that
    is not available, on the citation title if the title is a domain.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

REDIRECT_HOSTS = ("vertexaisearch.cloud.google.com",)
_DOMAIN_LIKE = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$", re.IGNORECASE)
# Same-length replacements only, so offsets in the normalized text match the original.
_NORMALIZE = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', " ": " "})


def normalize(text: str) -> str:
    return (text or "").translate(_NORMALIZE)


def _split(cell: str | None) -> list[str]:
    return [p.strip() for p in (cell or "").split("|") if p.strip()]


def term_regex(term: str) -> re.Pattern | None:
    t = normalize(term).strip().rstrip(".").strip()
    words = t.split()
    if not words:
        return None
    body = r"[\s\-‐]+".join(re.escape(w) for w in words)
    return re.compile(r"(?<!\w)" + body + r"(?!\w)", re.IGNORECASE)


@dataclass
class Watched:
    name: str
    aliases: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    is_member: bool = True
    _patterns: list = field(default_factory=list, repr=False)

    def patterns(self) -> list[re.Pattern]:
        if not self._patterns:
            seen = set()
            for term in [self.name] + self.aliases:
                key = normalize(term).strip().rstrip(".").lower()
                if key and key not in seen:
                    seen.add(key)
                    rx = term_regex(term)
                    if rx:
                        self._patterns.append(rx)
        return self._patterns


def load_names(path: str | Path) -> list[Watched]:
    out: list[Watched] = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = (row.get("name") or "").strip()
            if not name or name.startswith("#"):
                continue
            member = (row.get("is_member") or "1").strip().lower() in ("1", "yes", "true", "y")
            out.append(Watched(name=name, aliases=_split(row.get("aliases")),
                               domains=_split(row.get("domains")), is_member=member))
    return out


def merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for s, e in sorted(spans):
        if merged and s < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def find_spans(text: str, watched: Watched) -> list[tuple[int, int]]:
    norm = normalize(text)
    spans: list[tuple[int, int]] = []
    for rx in watched.patterns():
        spans.extend((m.start(), m.end()) for m in rx.finditer(norm))
    return merge_spans(spans)


def host_and_path(url: str) -> tuple[str, str]:
    url = (url or "").strip()
    if not url:
        return "", ""
    if "://" not in url:
        url = "https://" + url
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
    except ValueError:
        return "", ""
    if host.startswith("www."):
        host = host[4:]
    return host, parts.path or ""


def domain_matches(url: str, domain_entry: str) -> bool:
    dh, dp = host_and_path(domain_entry)
    uh, up = host_and_path(url)
    if not dh or not uh:
        return False
    if not (uh == dh or uh.endswith("." + dh)):
        return False
    dp = dp.rstrip("/")
    if dp:
        return up.lower().startswith(dp.lower())
    return True


def effective_url(citation: dict) -> str:
    """The URL to match: resolved redirect, else the URL, else a domain-like title for redirects."""
    resolved = (citation.get("resolved_url") or "").strip()
    if resolved:
        return resolved
    url = (citation.get("url") or "").strip()
    host, _ = host_and_path(url)
    if host in REDIRECT_HOSTS:
        title = (citation.get("title") or "").strip().lower()
        if title.startswith("www."):
            title = title[4:]
        if _DOMAIN_LIKE.match(title):
            return "https://" + title + "/"
    return url


def citation_domain(citation: dict) -> str:
    host, _ = host_and_path(effective_url(citation))
    return host


@dataclass
class Mention:
    appears: bool = False
    first_offset: int | None = None
    mention_count: int = 0
    rank_among_watched: int | None = None
    cited: bool = False
    cited_urls: list[str] = field(default_factory=list)


def find_mentions(text: str, watched_list: list[Watched], citations: list[dict]) -> dict[str, Mention]:
    results: dict[str, Mention] = {}
    for w in watched_list:
        spans = find_spans(text, w)
        cited_urls: list[str] = []
        for c in citations or []:
            eff = effective_url(c)
            if any(domain_matches(eff, d) for d in w.domains):
                # Record the readable address: the resolved target of a redirect link if known.
                u = (c.get("resolved_url") or "").strip() or c.get("url") or eff
                if u not in cited_urls:
                    cited_urls.append(u)
        results[w.name] = Mention(appears=bool(spans), first_offset=spans[0][0] if spans else None,
                                  mention_count=len(spans), cited=bool(cited_urls), cited_urls=cited_urls)
    ranked = sorted((m for m in results.values() if m.appears), key=lambda m: m.first_offset)
    for i, m in enumerate(ranked, 1):
        m.rank_among_watched = i
    return results
