import os
from pathlib import Path
import torch
import whisper

AUDIO_DIR = r"C:\proscan\Recordings\09-25-25\Middlesex"
MODEL_SIZE = "large-v3"  # tiny/base/small/medium/large-v3
LANGUAGE = "en"
EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}
SKIP_IF_TXT_EXISTS = True

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
model = whisper.load_model(MODEL_SIZE, device=DEVICE)

INITIAL_PROMPT = (
    "This is a police radio dispatch. Use concise wording and correct common radio terms: "
    "Newton, Cambridge, Waltham, Middlesex, BOLO, PD, FD, EMS, B&E, domestic, larceny, "
    "stop, plate, unit, sector, priority, signal, perimeter, caller, RP, RO, address, "
    "intersection, Route 9, Mass Pike, I-95, I-90, warrant, Harvard, MIT, Tufts."
)


def transcribe(audio_path: Path) -> str:
    result = model.transcribe(
        str(audio_path),
        language=LANGUAGE,
        fp16=(DEVICE == "cuda"),
        temperature=0.0,
        beam_size=1,
        best_of=1,
        condition_on_previous_text=False,
        initial_prompt=INITIAL_PROMPT,
        no_speech_threshold=0.6,
        logprob_threshold=-1.0,
        compression_ratio_threshold=2.4,
    )
    return result["text"].strip()


def main():
    root = Path(AUDIO_DIR)
    files = sorted(
        [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in EXTS],
        key=lambda p: p.name,
    )
    if not files:
        print("No audio files found.")
        return

    print(f"Found {len(files)} files in {root}")
    for p in files:
        out_txt = p.with_suffix(p.suffix + ".txt")
        if SKIP_IF_TXT_EXISTS and out_txt.exists() and out_txt.stat().st_size > 0:
            print(f"[skipped] {p}")
            continue

        try:
            print(f"[transcribing] {p}")
            text = transcribe(p)
            out_txt.write_text(text, encoding="utf-8")
            print(text, "\n")
        except Exception as e:
            print(f"[error] {p}: {e}")


if __name__ == "__main__":
    main()
