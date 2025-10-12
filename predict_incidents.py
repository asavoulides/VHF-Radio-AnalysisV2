
#!/usr/bin/env python3
"""
Predict incident type for new transcripts/rows using the saved model.

Usage:
  python predict_incidents.py --model_dir model_out \
      --transcript "units responding to a structure fire..." \
      --department "Newton Fire" --channel "Fire Ops 1" --time "2025-10-06T14:33:00-04:00"

  # Or, run on a CSV with columns: transcript, department, channel, time_recorded
  python predict_incidents.py --model_dir model_out --csv new_calls.csv
"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import tensorflow as tf
from datetime import datetime
import pandas as pd

def parse_time_to_meta(timestr):
    try:
        dt = pd.to_datetime(timestr, utc=True)
        hour = int(dt.hour)
        wday = int(dt.weekday())
    except Exception:
        hour, wday = 0, 0
    return hour, wday

def predict_rows(model, rows):
    x = {
        'transcript': rows['transcript'].astype(str).values,
        'department': rows['department'].fillna('').astype(str).values,
        'channel': rows['channel'].fillna('').astype(str).values,
        'hour': rows['hour'].astype('float32').values.reshape(-1,1),
        'weekday': rows['weekday'].astype('float32').values.reshape(-1,1),
    }
    probs = model.predict(x, verbose=0)
    pred_ids = probs.argmax(axis=1)
    confidences = probs.max(axis=1)
    return pred_ids, confidences, probs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model_dir', default='model_out', help='Directory with incident_classifier.keras and label_map.json')
    ap.add_argument('--transcript', default=None)
    ap.add_argument('--department', default="")
    ap.add_argument('--channel', default="")
    ap.add_argument('--time', default=None, help='ISO datetime string')
    ap.add_argument('--csv', default=None, help='CSV file with columns transcript,department,channel,time_recorded')
    args = ap.parse_args()

    model_dir = Path(args.model_dir)
    model = tf.keras.models.load_model(str(model_dir / 'incident_classifier.keras'))
    with open(model_dir / 'label_map.json', 'r', encoding='utf-8') as f:
        lm = json.load(f)
    labels = lm['labels']

    if args.csv:
        df = pd.read_csv(args.csv)
        if 'time_recorded' not in df.columns:
            df['time_recorded'] = None
        meta = df['time_recorded'].apply(lambda t: parse_time_to_meta(t))
        df['hour'] = [h for h,_ in meta]
        df['weekday'] = [w for _,w in meta]
        df['department'] = df.get('department','').fillna('')
        df['channel'] = df.get('channel','').fillna('')
        pred_ids, confs, _ = predict_rows(model, df.rename(columns={'time_recorded':'time'}))
        df['pred_label'] = [labels[i] for i in pred_ids]
        df['confidence'] = confs
        out = model_dir / 'predictions.csv'
        df.to_csv(out, index=False)
        print("Saved predictions to:", out)
    else:
        if not args.transcript:
            raise SystemExit("Provide --transcript or --csv")
        hour, wday = parse_time_to_meta(args.time)
        one = pd.DataFrame([{
            'transcript': args.transcript,
            'department': args.department or "",
            'channel': args.channel or "",
            'hour': hour,
            'weekday': wday
        }])
        pred_ids, confs, _ = predict_rows(model, one)
        pred = labels[int(pred_ids[0])]
        print(f"Prediction: {pred}  (confidence={confs[0]:.3f})")

if __name__ == '__main__':
    main()
