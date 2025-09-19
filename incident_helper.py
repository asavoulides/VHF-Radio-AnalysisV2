import re
import json
import sqlite3
import textwrap
import ollama

# ----- Canonical label set -----
LABELS = [
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
LABEL_SET = set(LABELS)

# ----- LLM instructions (LLM decides incident vs unknown) -----
SYSTEM = textwrap.dedent(
    """
You are a dispatcher-grade classifier for police/fire radio transcripts.

Return ONLY this JSON object (no extra text):
{"label":"<one-of-allowed-labels>"}

Allowed labels (choose exactly one):
- Assault/Domestic
- Theft/Burglary
- Disturbance/Noise
- Weapons/Shots Fired
- Traffic Stop
- Motor Vehicle Accident
- Medical
- Fire Alarm
- Structure Fire
- Brush/Vehicle Fire
- Gas/Electrical Hazard
- Wires Down
- Hazmat
- Animal Complaint
- Welfare Check
- Suspicious Activity
- Missing Person
- Alarm (Burglar/Panic)
- unknown

Decision rules (the model decides):
1) If the transmission is purely administrative/status/test (e.g., "clear of hospital", "back in service", "copy", "roger", availability/command updates) and does not describe any incident: return "unknown".
2) Medical vs Fire: patient condition, injury, sickness, overdose, fall, chest pain, vomiting, psych evaluation transport → "Medical".
3) Welfare Check: well-being check, suicidal ideation, elderly not answering → "Welfare Check".
4) CO/smoke detectors, automatic alarms without confirmed fire → "Fire Alarm".
5) Confirmed active fire in a structure → "Structure Fire".
6) Brush/vehicle/dumpster fire → "Brush/Vehicle Fire".
7) Wires down/arcing → "Wires Down".
8) Odor of gas/electrical hazard inside (not exterior wires) → "Gas/Electrical Hazard".
9) Suspicious package/object: if hazardous materials clearly involved → "Hazmat"; if merely suspicious/unknown → "Suspicious Activity".
10) Shoplifting/larceny/burglary → "Theft/Burglary".
11) Disturbance/Noise: disputes/parties/disorderly without assault/weapons.
12) Assault/Domestic: assault/domestic violence; prioritize over Disturbance/Noise.
13) Weapons/Shots Fired: shots heard or weapon brandished.
14) Traffic Stop: officer-initiated stop (not crashes).
15) Motor Vehicle Accident: crash/MVA (even if injuries).
16) Alarm (Burglar/Panic): burglar/panic/hold-up alarms (NOT fire alarms).
17) Animal Complaint: animal issues.
18) Missing Person: missing/endangered person reports.
19) If an incident clearly exists but the subtype is unclear → "unknown".
20) If the transcript is empty/garbled or clearly no incident → "unknown".

Output policy:
- Output exactly JSON like {"label":"Medical"}; no explanations or extra keys.
"""
).strip()

# Few-shot examples including admin/status -> unknown (LLM learns this, not a prefilter)
FEWSHOTS = [
    ("We're clear of the hospital and available in the city.", "unknown"),
    ("Maintain command for a few minutes; assisting the medic.", "unknown"),
    (
        "Check the well-being of a female with suicidal ideation at 649 Quentin Place.",
        "Welfare Check",
    ),
    ("Medic 2 respond for psych eval, clear to enter per PD.", "Medical"),
    (
        "Black cylinder-shaped item on the sidewalk, caller unsure what it is.",
        "Suspicious Activity",
    ),
    ("Residential CO detector activation at 206 Winslow Road.", "Fire Alarm"),
    (
        "Shoplifting at Bloomingdale's, sunglasses taken, suspect headed toward the mall.",
        "Theft/Burglary",
    ),
    ("Unit 12 out on a traffic stop, blue Honda Civic.", "Traffic Stop"),
    (
        "Two-car crash at Beacon and Centre, no entrapment reported.",
        "Motor Vehicle Accident",
    ),
    ("Vehicle on fire on the shoulder, flames visible.", "Brush/Vehicle Fire"),
]


def build_user_prompt(transcript: str) -> str:
    label_list = ", ".join(LABELS)
    examples = [
        f'Example Incident: {t}\nExample Output: {{"label":"{y}"}}' for t, y in FEWSHOTS
    ]
    base = (
        "Classify the following radio transcript using EXACTLY one allowed label. "
        'If there is no incident (admin/status/test only), return "unknown". '
        'If there is an incident but the type is unclear, use "unknown". '
        f"Allowed: {label_list}. "
        'Return ONLY JSON like {"label":"Medical"}.\n\nIncident:\n'
    )
    return "\n".join(examples) + "\n\n" + base + (transcript or "")


THINK_RE = re.compile(r"<think>.*?</think>", flags=re.DOTALL)


def clean_reasoning(text: str) -> str:
    return THINK_RE.sub("", text).strip()


def parse_label(raw: str) -> str:
    raw = clean_reasoning(raw)
    m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if m:
        raw = m.group(0)
    try:
        obj = json.loads(raw)
        label = obj.get("label", "").strip()
    except Exception:
        # Fallback: find a known label in plain text
        for lab in LABELS:
            if re.search(rf"\b{re.escape(lab)}\b", raw, flags=re.IGNORECASE):
                return lab
        return "unknown"

    alias_map = {
        "burglary": "Theft/Burglary",
        "larceny": "Theft/Burglary",
        "shots fired": "Weapons/Shots Fired",
        "weapons": "Weapons/Shots Fired",
        "traffic": "Traffic Stop",
        "mva": "Motor Vehicle Accident",
        "burglar alarm": "Alarm (Burglar/Panic)",
        "panic alarm": "Alarm (Burglar/Panic)",
        "fire": "Structure Fire",
        "other/unknown": "unknown",
    }
    low = label.lower()
    if low in alias_map:
        label = alias_map[low]

    if label not in LABEL_SET:
        for lab in LABELS:
            if lab.lower() == low:
                return lab
        return "unknown"
    return label


def classify_incident(transcript: str) -> str:
    """
    LLM-only path: every transcript goes to the model.
    The model decides incident vs unknown; we just enforce JSON and validate.
    """
    user_prompt = build_user_prompt(transcript)

    def _call():
        resp = ollama.chat(
            model="deepseek-r1",
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            format="json",  # ask Ollama for strict JSON
            options={
                "temperature": 0.0,  # deterministic
                "top_p": 1.0,
                "num_ctx": 2048,
            },
            stream=False,
        )
        return resp.get("message", {}).get("content", "")

    out = _call()
    label = parse_label(out)
    if label not in LABEL_SET:
        # Retry with super-minimal prompt if parsing failed
        short_prompt = (
            'Return ONLY {"label":"<label>"} for this transcript.\n'
            f"Allowed: {', '.join(LABELS)}.\n\nTranscript:\n{transcript or ''}"
        )
        resp = ollama.chat(
            model="deepseek-r1",
            messages=[
                {
                    "role": "system",
                    "content": 'Return ONLY compact JSON like {"label":"Medical"}.',
                },
                {"role": "user", "content": short_prompt},
            ],
            format="json",
            options={"temperature": 0.0, "top_p": 1.0, "num_ctx": 1024},
            stream=False,
        )
        label = parse_label(resp.get("message", {}).get("content", ""))
    
    return label if label in LABEL_SET else "unknown"

