import os, googlemaps
from dotenv import load_dotenv
from urllib.parse import quote_plus
from __future__ import annotations
import re
import json
from typing import Optional, List, Dict
from dataclasses import dataclass
from ollama import chat


load_dotenv()
gmaps = googlemaps.Client(key=os.getenv("Google_API_KEY"))
# =========================
# Tunables (Heavy model)
# =========================
PRIMARY_MODEL = (
    "qwen2.5:32b-instruct"  # heavy, accurate; use Q4_K_M quant for 24GB VRAM
)

OLLAMA_OPTIONS = {
    "temperature": 0,
    "top_k": 1,
    "top_p": 1,
    "num_predict": 64,  # addresses are short
    "num_ctx": 8192,  # headroom for messy transcripts
    "repeat_penalty": 1.05,
}


# =========================
# Regex fast path
# =========================

# Common US street suffixes (non-capturing)
ST_SUFFIX = (
    r"(?:St(?:\.|reet)?|Ave(?:\.|nue)?|Rd(?:\.|oad)?|Blvd(?:\.)?|Boulevard|"
    r"Ln(?:\.|ane)?|Dr(?:\.|ive)?|Ct(?:\.|ourt)?|Pl(?:\.|ace)?|Ter(?:\.|race)?|"
    r"Pkwy(?:\.)?|Parkway|Cir(?:\.|cle)?|Hwy(?:\.)?|Highway)"
)

# (1) Full numbered street address (with optional unit/city/state/zip)
RE_ADDR_NUMBERED = re.compile(
    rf"""\b
    (?P<number>\d{{1,6}})\s+
    (?P<street>(?:[A-Za-z0-9.\-']+\s+){{0,5}}[A-Za-z0-9.\-']+)\s+
    (?P<suf>{ST_SUFFIX})\b
    (?:\s*(?P<unit>(?:Apt|Unit|\#)\s*[A-Za-z0-9\-]+))?
    (?:\s*,?\s*(?P<city>[A-Za-z.\- ]{{2,40}}))?
    (?:\s*,?\s*(?P<state>AL|AK|AS|AZ|AR|CA|CO|CT|DC|DE|FL|GA|GU|HI|IA|ID|IL|IN|KS|KY|LA|
                MA|MD|ME|MI|MN|MO|MP|MS|MT|NC|ND|NE|NH|NJ|NM|NV|NY|OH|OK|OR|PA|
                PR|RI|SC|SD|TN|TX|UT|VA|VI|VT|WA|WI|WV))?
    (?:\s*,?\s*(?P<zip>\d{{5}}(?:-\d{{4}})?))?
    """,
    re.IGNORECASE | re.VERBOSE,
)

# (2) Intersection (“Boylston St & Arlington St”, “at Main St and 3rd Ave”)
RE_INTERSECTION = re.compile(
    rf"""\b
    (?P<a>(?:[A-Za-z0-9.\-']+\s+){{0,3}}[A-Za-z0-9.\-']+\s+{ST_SUFFIX})
    \s*(?:&|and|at|/)\s*
    (?P<b>(?:[A-Za-z0-9.\-']+\s+){{0,3}}[A-Za-z0-9.\-']+\s+{ST_SUFFIX})\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# (3) Highway + exit / mm (I-95 SB by exit 21, Route 2 EB at mm 54.3)
RE_HIGHWAY = re.compile(
    r"""
    \b(
        (?:I-\d{1,3}|Interstate\s+\d{1,3}|Rt\.?|Route\s+\d{1,3}|Rte\.?\s+\d{1,3})
        (?:\s?(?:NB|SB|EB|WB))?
        (?:\s*(?:by|at|near)\s*(?:exit\s*\d+[A-Za-z]?|mm\s*\d+(?:\.\d+)?))?
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# (4) Street-only
RE_STREET_ONLY = re.compile(
    rf"""\b
    (?P<street>(?:[A-Za-z0-9.\-']+\s+){{0,5}}[A-Za-z0-9.\-']+)\s+
    (?P<suf>{ST_SUFFIX})\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# (5) Named area / neighborhood (“Harvard Square”, “Newton Corner area”)
RE_NEIGHBORHOOD = re.compile(
    r"""\b
    (?P<place>[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,2})
    (?:\s+(?P<tag>area|square|corner|center|centre))?
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _regex_extract(text: str) -> Optional[str]:
    """
    Quick deterministic wins, in priority order aligned with the spec.
    """
    # 1) Full numbered address
    m = RE_ADDR_NUMBERED.search(text)
    if m:
        parts = [m.group("number"), m.group("street"), m.group("suf")]
        if m.group("unit"):
            parts.append(m.group("unit"))
        out = " ".join(p for p in parts if p).strip()
        tail = " ".join(
            x for x in [m.group("city"), m.group("state"), m.group("zip")] if x
        )
        return f"{out}, {tail}" if tail else out

    # 2) Intersection
    m = RE_INTERSECTION.search(text)
    if m:
        return f"{m.group('a')} & {m.group('b')}"

    # 3) Highway / exit
    m = RE_HIGHWAY.search(text)
    if m:
        return m.group(1).strip()

    # 4) Street-only
    m = RE_STREET_ONLY.search(text)
    if m:
        return f"{m.group('street')} {m.group('suf')}"

    # 5) Named area
    # To avoid grabbing random proper nouns, require either a tag OR phrase appears with common area words in the text
    for m in RE_NEIGHBORHOOD.finditer(text):
        span = m.group(0).strip()
        # Heuristic: prefer ones that include a tag or are followed/preceded by "area/center/square/corner"
        if m.group("tag"):
            return span
    # Fallback second pass: accept bare place if nothing else matched
    m = RE_NEIGHBORHOOD.search(text)
    if m:
        return m.group(0).strip()

    return None


# =========================
# LLM Prompt (heavy, strict)
# =========================

SYSTEM_PROMPT = (
    "You extract addresses from short police radio transcripts. "
    "Return ONLY the most specific location SUBSTRING that already exists in the user text. "
    "Do not normalize, infer, or add punctuation not present in that substring. "
    "Priority: numbered street address > intersection > highway+exit/mm > street-only > named area; "
    "if nothing is location-like, return NONE. "
    'Output strict JSON exactly as: {"address":"<substring or NONE>"} with no extra keys.'
)

FEWSHOTS: List[Dict[str, str]] = [
    # Full address with unit
    {
        "role": "user",
        "content": "Caller says suspect ran into 125 Commonwealth Ave Apt 3B, door was propped open.",
    },
    {"role": "assistant", "content": '{"address":"125 Commonwealth Ave Apt 3B"}'},
    # Intersection
    {
        "role": "user",
        "content": "MVC at Boylston St and Arlington St, both cars drivable.",
    },
    {"role": "assistant", "content": '{"address":"Boylston St and Arlington St"}'},
    # Highway + exit
    {
        "role": "user",
        "content": "Vehicle stopped on I-95 SB by exit 21, hazard lights on.",
    },
    {"role": "assistant", "content": '{"address":"I-95 SB by exit 21"}'},
    # Street-only vs neighborhood
    {
        "role": "user",
        "content": "Suspicious person walking from Tremont Street toward the Newton Corner area.",
    },
    {"role": "assistant", "content": '{"address":"Tremont Street"}'},
    # Named area when nothing more specific
    {
        "role": "user",
        "content": "Loud party in the Harvard Square area, caller can meet outside the station.",
    },
    {"role": "assistant", "content": '{"address":"Harvard Square area"}'},
]


def _ask_heavy_llm(text: str) -> str:
    """
    Single heavy-model call. No fallback.
    """
    resp = chat(
        model=PRIMARY_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            *FEWSHOTS,
            {"role": "user", "content": text},
        ],
        options=OLLAMA_OPTIONS,
        format="json",
    )
    raw = resp["message"]["content"]
    try:
        obj = json.loads(raw)
        addr = (obj.get("address") or "").strip()
        return addr if addr else "NONE"
    except Exception:
        # Last-ditch salvage if the model leaked text
        m = re.search(r'"address"\s*:\s*"([^"]*)"', raw)
        return m.group(1).strip() if m else "NONE"

# =========================
# Public API
# =========================
def extract_address(text: str) -> str:
    """
    Public API: returns the most specific address-like span or "NONE".
    """
    hit = _regex_extract(text)
    if hit:
        return hit
    return _ask_heavy_llm(text)


def geocode_newton(address: str):
    q = f"{address}, Newton, MA"
    res = gmaps.geocode(q, components={"administrative_area": "MA", "country": "US"})
    if not res:
        return None
    r = res[0]
    loc = r["geometry"]["location"]
    fa, pid = r["formatted_address"], r.get("place_id")
    url = (
        f"https://www.google.com/maps/search/?api=1&query={quote_plus(fa)}&query_place_id={pid}"
        if pid
        else None
    )
    return loc["lat"], loc["lng"], fa, url


if __name__ == "__main__":
    lat, lng, fa, url = geocode_newton("192 evelyn rd ")
    print(lat, lng)
    print(fa)
    print(url)
