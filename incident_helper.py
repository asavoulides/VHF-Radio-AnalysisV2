import sqlite3
import random

DB_PATH = "audio_metadata_BACKUP.db"

"""
Advanced incident classifier using Ollama with:
- Robust schema-constrained prompting (JSON mode with strict keys)
- Domain glossary and edge-case rules (fast-path keyword classifier)
- Few-shot exemplars
- Deterministic decoding + retries and graceful fallbacks
- Canonical label mapping & sanitization
- Optional probability-style scores (model-estimated)
- Batch APIs with simple concurrency

Requirements:
  pip install python-dotenv ollama tenacity rapidfuzz
"""

import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from dotenv import load_dotenv
from ollama import chat
from ollama import ChatResponse
from rapidfuzz import fuzz, process as rf_process
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

# ------------------------------
# Env & constants
# ------------------------------
load_dotenv()

LABELS: List[str] = [
    "Assault/Domestic",
    "Theft/Burglary",
    "Disturbance/Noise",
    "Weapons/Shots Fired",
    "Traffic Stop",
    "Motor Vehicle Accident",
    "Medical",
    "Fire Alarm",
    "Structure Fire",
    "Brush/Vehicle Fire",
    "Gas/Electrical Hazard",
    "Wires Down",
    "Hazmat",
    "Animal Complaint",
    "Welfare Check",
    "Suspicious Activity",
    "Missing Person",
    "Alarm (Burglar/Panic)",
    "unknown",
]

# We keep a lowercased version for matching
_LABELS_LOWER = [l.lower() for l in LABELS]

# Synonym map → canonical label (lowercased keys)
_SYNONYMS = {
    # Assault / Domestic
    "domestic": "Assault/Domestic",
    "assault": "Assault/Domestic",
    "battery": "Assault/Domestic",
    "fight": "Assault/Domestic",
    # Theft
    "larceny": "Theft/Burglary",
    "robbery": "Theft/Burglary",
    "shoplift": "Theft/Burglary",
    "break-in": "Theft/Burglary",
    "b&e": "Theft/Burglary",
    # Disturbance / Noise
    "noise": "Disturbance/Noise",
    "disturbance": "Disturbance/Noise",
    "dispute": "Disturbance/Noise",
    # Weapons
    "shots fired": "Weapons/Shots Fired",
    "gunshots": "Weapons/Shots Fired",
    "weapon": "Weapons/Shots Fired",
    # Traffic
    "traffic stop": "Traffic Stop",
    "stop vehicle": "Traffic Stop",
    # MVA
    "crash": "Motor Vehicle Accident",
    "mva": "Motor Vehicle Accident",
    "collision": "Motor Vehicle Accident",
    # Medical
    "medic": "Medical",
    "ems": "Medical",
    "overdose": "Medical",
    # Fire
    "alarm": "Fire Alarm",
    "structure fire": "Structure Fire",
    "house fire": "Structure Fire",
    "car fire": "Brush/Vehicle Fire",
    "brush": "Brush/Vehicle Fire",
    # Gas/Electrical
    "gas leak": "Gas/Electrical Hazard",
    "odor of gas": "Gas/Electrical Hazard",
    "electrical": "Gas/Electrical Hazard",
    # Wires
    "wires down": "Wires Down",
    # Hazmat
    "hazmat": "Hazmat",
    "spill": "Hazmat",
    # Animal
    "dog": "Animal Complaint",
    "animal": "Animal Complaint",
    # Welfare
    "well-being": "Welfare Check",
    "welfare": "Welfare Check",
    "wellbeing": "Welfare Check",
    # Suspicious
    "suspicious": "Suspicious Activity",
    # Missing
    "missing": "Missing Person",
    # Alarm
    "burglar": "Alarm (Burglar/Panic)",
    "panic alarm": "Alarm (Burglar/Panic)",
}

# Simple keyword regexes for fast-path rule classification
_RULES: List[Tuple[str, str]] = [
    (r"\\b(domestic|assault|battery|fight)\\b", "Assault/Domestic"),
    (
        r"\\b(larceny|robbery|shoplift|break[- ]?in|b&e|burglary|stolen)\\b",
        "Theft/Burglary",
    ),
    (r"\\b(noise|disturbance|dispute|loud music)\\b", "Disturbance/Noise"),
    (r"\\b(shots? fired|gunshots?|weapon|firearm)\\b", "Weapons/Shots Fired"),
    (r"\\b(traffic stop|stop vehicle)\\b", "Traffic Stop"),
    (
        r"\\b(motor vehicle accident|mva|crash|collision|fender bender)\\b",
        "Motor Vehicle Accident",
    ),
    (r"\\b(overdose|medic|ems|unconscious|difficulty breathing|cardiac)\\b", "Medical"),
    (r"\\b(fire alarm|pull station|alarm activation)\\b", "Fire Alarm"),
    (r"\\b(structure fire|house fire|building fire)\\b", "Structure Fire"),
    (r"\\b(brush fire|car fire|vehicle fire|dumpster fire)\\b", "Brush/Vehicle Fire"),
    (
        r"\\b(gas leak|odor of gas|natural gas|electrical hazard)\\b",
        "Gas/Electrical Hazard",
    ),
    (r"\\b(wires? down|utility wires?)\\b", "Wires Down"),
    (r"\\b(hazmat|chemical spill|hazardous material)\\b", "Hazmat"),
    (r"\\b(dog|coyote|animal complaint|animal control)\\b", "Animal Complaint"),
    (r"\\b(welfare check|well[- ]?being|section 12)\\b", "Welfare Check"),
    (r"\\b(suspicious|prowler|peeping|tampering)\\b", "Suspicious Activity"),
    (r"\\b(missing person|missing juvenile|silver alert)\\b", "Missing Person"),
    (r"\\b(burglar alarm|panic alarm|hold[- ]?up alarm)\\b", "Alarm (Burglar/Panic)"),
]


@dataclass
class LLMResult:
    label: str
    rationale: Optional[str] = None
    scores: Optional[Dict[str, float]] = None  # pseudo-probabilities from the model


def _normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _canonicalize(label: str) -> str:
    """Map arbitrary label text to the closest canonical LABELS.
    Uses direct match, synonyms, and fuzzy fallback. Defaults to 'unknown'.
    """
    raw = (label or "").strip().lower()
    if not raw:
        return "unknown"
    # direct match
    if raw in _LABELS_LOWER:
        return LABELS[_LABELS_LOWER.index(raw)]
    # synonyms
    for k, v in _SYNONYMS.items():
        if k in raw:
            return v
    # fuzzy
    best, score, _ = rf_process.extractOne(raw, LABELS, scorer=fuzz.WRatio)
    return best if (score or 0) >= 85 else "unknown"


def _rules_fast_path(text: str) -> Optional[str]:
    t = text.lower()
    for pat, lab in _RULES:
        if re.search(pat, t):
            return lab
    return None


# ------------------------------
# Prompting
# ------------------------------

_GLOSSARY = {
    "Assault/Domestic": "Violence or threat thereof between individuals, incl. domestic/family incidents.",
    "Theft/Burglary": "Taking property, shoplifting, robbery, break-ins (B&E).",
    "Disturbance/Noise": "Disputes, loud noise, nuisance calls without violence.",
    "Weapons/Shots Fired": "Reports of firearms, gunshots, armed subjects.",
    "Traffic Stop": "Officer-initiated vehicle stop for violations.",
    "Motor Vehicle Accident": "Crashes, collisions, MVAs (with/without injuries).",
    "Medical": "Medical aid, overdoses, EMS responses.",
    "Fire Alarm": "Fire alarm activations without confirmed fire.",
    "Structure Fire": "Confirmed or likely building/structure fire.",
    "Brush/Vehicle Fire": "Fires involving vegetation or vehicles/dumpsters.",
    "Gas/Electrical Hazard": "Odor of gas, gas leaks, electrical hazards.",
    "Wires Down": "Downed utility wires creating hazards.",
    "Hazmat": "Hazardous materials/chemical incidents.",
    "Animal Complaint": "Animal control, dangerous/loose animals.",
    "Welfare Check": "Requested check on person’s wellbeing.",
    "Suspicious Activity": "Prowlers, suspicious persons/vehicles, tampering.",
    "Missing Person": "Missing/overdue person or juvenile.",
    "Alarm (Burglar/Panic)": "Security/panic/hold-up alarms (non-fire).",
    "unknown": "Insufficient info to determine category.",
}

_LABEL_LIST_BULLET = "\n".join(f"- {k}: {_GLOSSARY[k]}" for k in LABELS)

SYSTEM_PROMPT = f"""
You are a disciplined incident labeler for public safety radio logs. You MUST:
- Read the transcript and pick exactly ONE label from the allowed set.
- If uncertain, choose "unknown".
- Use the glossary definitions to disambiguate.
- Return STRICT JSON with keys: label (string), rationale (string, concise), scores (object of label→0..1).
Allowed labels and definitions:\n{_LABEL_LIST_BULLET}
"""

# Few-shot exemplars (concise & diverse). Keep short for context window.
FEW_SHOTS: List[Tuple[str, str]] = [
    ("Caller reports loud party, neighbors arguing, no weapons.", "Disturbance/Noise"),
    (
        "Two-car collision with airbag deployment on Washington St.",
        "Motor Vehicle Accident",
    ),
    ("Panic alarm at the bank on Main St.", "Alarm (Burglar/Panic)"),
    ("Odor of gas in the basement, requesting utility.", "Gas/Electrical Hazard"),
    ("Male yelling he has a gun; neighbors heard two shots.", "Weapons/Shots Fired"),
    ("Check on elderly male not answering phone since yesterday.", "Welfare Check"),
    ("Possible shoplifting in progress at the pharmacy.", "Theft/Burglary"),
    ("Brush fire behind the school, small area burning.", "Brush/Vehicle Fire"),
    ("Residential fire alarm activation, no smoke visible.", "Fire Alarm"),
    ("Female reports ex-boyfriend shoved her; minor injuries.", "Assault/Domestic"),
]

# ------------------------------
# LLM call with retries & JSON-mode
# ------------------------------


class LLMError(Exception):
    pass


def _safe_json_loads(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Attempt to extract JSON object from messy output
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        raise


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=2.0),
    retry=retry_if_exception_type(LLMError),
)
def _query_llm(
    transcript: str, model: str = os.getenv("OLLAMA_MODEL", "qwen2.5")
) -> LLMResult:
    user_prompt = {
        "role": "user",
        "content": (
            "You will classify the following radio transcript into ONE label.\n"
            "Transcript:"
            f"\n\n{_normalize_text(transcript)}\n\n"
            'Respond ONLY with a JSON object: {"label": string, "rationale": string, "scores": object}.\n'
            f"The label MUST be one of: {', '.join(LABELS)}."
        ),
    }

    # Insert few shots as system-style mini-context to reduce verbosity
    examples = "\n".join([f"- '{t}' → {lab}" for t, lab in FEW_SHOTS])
    shots_prompt = {
        "role": "system",
        "content": f"Examples (transcript → label):\n{examples}",
    }

    try:
        resp: ChatResponse = chat(
            model=model,
            options={
                "temperature": 0.1,
                "top_p": 0.9,
                "seed": 7,
                "num_ctx": 4096,
                "stop": ["\n\n\n"],
                "format": "json",  # ask for strict JSON when supported
            },
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                shots_prompt,
                user_prompt,
            ],
        )
    except Exception as e:
        raise LLMError(str(e))

    text = (resp.get("message", {}) or {}).get("content", "").strip()
    if not text:
        raise LLMError("empty response")

    try:
        obj = _safe_json_loads(text)
    except Exception as e:
        # try a strict re-ask once in current retry attempt by coercing format off
        try:
            resp2: ChatResponse = chat(
                model=model,
                options={"temperature": 0.1, "top_p": 0.9, "seed": 7, "num_ctx": 4096},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    shots_prompt,
                    {
                        "role": "user",
                        "content": (
                            'STRICT: Reply ONLY with JSON object {"label":, "rationale":, "scores":}.\n\n'
                            f"Transcript: {_normalize_text(transcript)}"
                        ),
                    },
                ],
            )
            obj = _safe_json_loads((resp2.get("message", {}) or {}).get("content", ""))
        except Exception as e2:
            raise LLMError(
                f"Failed to parse JSON: {e}\nSecond attempt: {e2}\nRaw: {text[:400]}"
            )

    raw_label = obj.get("label", "unknown")
    rationale = obj.get("rationale")
    scores = obj.get("scores") if isinstance(obj.get("scores"), dict) else None
    return LLMResult(label=_canonicalize(raw_label), rationale=rationale, scores=scores)


# ------------------------------
# Public API
# ------------------------------


def classify_incident(transcript: str, *, use_rules_first: bool = True) -> str:
    if len(transcript.split()) < 5:
        return "unknown"
    """Classify a single transcript. Returns a canonical label from LABELS.

    - Fast path rules can immediately classify common cases without LLM cost.
    - Falls back to LLM with robust JSON prompt & canonicalization.
    """
    t = _normalize_text(transcript)
    if use_rules_first:
        rule_hit = _rules_fast_path(t)
        if rule_hit:
            return rule_hit

    try:
        res = _query_llm(t)
        return res.label
    except Exception:
        # As last resort do fuzzy match against synonyms if any keyword hit
        for k, v in _SYNONYMS.items():
            if k in t.lower():
                return v
        return "unknown"
