#!/usr/bin/env python3
"""
dbIncidentPopulate.py

Reclassify SQLite rows where:
  - incident_type = 'unknown'
  - transcript has > 5 words
Update incident_type via incident_helper.classify_incident(transcript).

Dashboard:
  - Task Board (phase status)
  - Progress + Stats (elapsed, throughput, pending)
  - Avg classification time (ms)
  - Current Transcript (live, truncated)
  - 3 Most Recent Classifications (id → label, ms, snippet)
  - Activity Feed (rolling log)
  - Commit batch notifications

Display modes:
  1) Live (Rich Live)           [default if TTY, or use --force-live]
  2) Soft Live (manual redraw)  [auto fallback if Live fails]
  3) Plain                      [--no-live or non-TTY without force]
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from collections import deque
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Optional, List, Tuple

# --- Terminal UI (Rich) ---
try:
    from rich.console import Console, RenderableType
    from rich.table import Table
    from rich.progress import (
        Progress,
        BarColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )
    from rich.panel import Panel
    from rich.live import Live
    from rich.align import Align
    from rich.columns import Columns
    from rich.errors import LiveError
    from rich import box
    from rich.text import Text
except ImportError as e:
    raise SystemExit("Missing dependency: rich\nInstall with: pip install rich") from e

console = Console()

# --- Classifier helper ---
try:
    from incident_helper import classify_incident  # type: ignore
except Exception as e:
    raise SystemExit(
        "Could not import incident_helper.classify_incident.\n"
        "Make sure incident_helper.py is on your PYTHONPATH."
    ) from e


# =======================
# Args
# =======================
def build_args() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Reclassify 'unknown' incidents where transcript > 5 words."
    )
    p.add_argument(
        "--db",
        default=r"C:\Users\alexa\OneDrive\Desktop\Folders\Scripts\Python\Local Police Scanner Analysis\Logs\audio_metadata.db",
        help="Path to SQLite DB",
    )
    p.add_argument("--table", default="audio_metadata", help="Table name")
    p.add_argument("--batch", type=int, default=1000, help="Commit every N updates")
    p.add_argument("--max-updates", type=int, default=None, help="Stop after N updates")
    p.add_argument("--dry-run", action="store_true", help="Preview only (no writes)")
    p.add_argument("--sample", type=int, default=5, help="Show up to N sample rows")
    p.add_argument("--id-col", default="id", help="Primary key column")
    p.add_argument("--transcript-col", default="transcript", help="Transcript column")
    p.add_argument("--incident-col", default="incident_type", help="Incident column")
    p.add_argument("--no-live", action="store_true", help="Disable Live dashboard")
    p.add_argument(
        "--force-live", action="store_true", help="Force-enable Live dashboard"
    )
    p.add_argument(
        "--log-every", type=int, default=200, help="Activity heartbeat cadence"
    )
    p.add_argument("--verbose-rows", action="store_true", help="Sparse per-row pings")
    p.add_argument("--soft-live-rate", type=float, default=8.0, help="Soft Live FPS")
    p.add_argument(
        "--no-transcript", action="store_true", help="Hide transcript text in UI"
    )
    p.add_argument(
        "--snippet-len", type=int, default=160, help="Transcript snippet length"
    )
    return p


# =======================
# DB helpers
# =======================
def sqlite_connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def count_candidates(
    conn: sqlite3.Connection, table: str, transcript_col: str, incident_col: str
) -> int:
    q = f"""
    SELECT COUNT(*) AS n
    FROM {table}
    WHERE {incident_col}='unknown'
      AND {transcript_col} IS NOT NULL
      AND LENGTH(TRIM({transcript_col})) > 0
      AND (
            (LENGTH(TRIM({transcript_col})) - LENGTH(REPLACE(TRIM({transcript_col}), ' ', '')) + 1) > 5
          )
    """
    cur = conn.execute(q)
    return int(cur.fetchone()["n"])


def fetch_candidates(
    conn: sqlite3.Connection,
    table: str,
    id_col: str,
    transcript_col: str,
    incident_col: str,
    limit: Optional[int] = None,
) -> List[sqlite3.Row]:
    q = f"""
    SELECT {id_col} AS id, {transcript_col} AS transcript, {incident_col} AS incident_type
    FROM {table}
    WHERE {incident_col}='unknown'
      AND {transcript_col} IS NOT NULL
      AND LENGTH(TRIM({transcript_col})) > 0
      AND (
            (LENGTH(TRIM({transcript_col})) - LENGTH(REPLACE(TRIM({transcript_col}), ' ', '')) + 1) > 5
          )
    """
    if limit:
        q += " LIMIT ?"
        cur = conn.execute(q, (limit,))
    else:
        cur = conn.execute(q)
    return list(cur.fetchall())


def update_incident(
    conn: sqlite3.Connection,
    table: str,
    incident_col: str,
    id_col: str,
    new_incident: str,
    row_id: int | str,
):
    q = f"UPDATE {table} SET {incident_col}=? WHERE {id_col}=?"
    conn.execute(q, (new_incident, row_id))


# =======================
# Presentation helpers
# =======================
def build_header_panel(db_path: Path, table: str, batch: int, dry: bool) -> Panel:
    return Panel.fit(
        f"[bold white]Reclassify Unknown Incidents[/bold white]\n"
        f"[dim]DB:[/dim] {db_path}\n"
        f"[dim]Table:[/dim] {table}  [dim]Batch:[/dim] {batch}  [dim]Dry Run:[/dim] {dry}",
        border_style="cyan",
    )


def build_candidates_panel(n: int) -> Panel:
    return Panel.fit(
        f"[bold]{n}[/bold] candidate rows (incident='unknown' & transcript > 5 words)",
        border_style="magenta",
    )


def truncate(text: str, n: int) -> str:
    return (text[:n] + "…") if len(text) > n else text


def build_sample_table(
    samples: List[Tuple[int | str, str, str]], snippet_len: int, hide_text: bool
) -> Table:
    t = Table(title="Sample Reclassifications", box=box.SIMPLE_HEAVY, expand=True)
    t.add_column("ID", no_wrap=True, style="bold")
    t.add_column("Predicted", style="green")
    if not hide_text:
        t.add_column("Transcript (truncated)", style="dim")
    for _id, pred, text in samples:
        if hide_text:
            t.add_row(str(_id), pred or "—")
        else:
            t.add_row(str(_id), pred or "—", truncate(text or "", snippet_len))
    return t


# ----- Task Board -----
@dataclass
class TaskState:
    db_connected: bool = False
    candidates_found: bool = False
    transcripts_ready: bool = False
    classification_running: bool = False
    classification_done: bool = False
    committing_running: bool = False
    committing_done: bool = False
    summary_written: bool = False


def status_emoji(flag: bool, running: bool = False) -> str:
    if running:
        return "⏳"
    return "✅" if flag else "•"


def build_task_board(
    ts: TaskState, processed: int, total: int, batches_done: int
) -> Panel:
    tbl = Table(box=box.SIMPLE, expand=True, show_header=False, pad_edge=False)
    tbl.add_row(
        "DB Connect",
        Text(
            status_emoji(ts.db_connected),
            style="green" if ts.db_connected else "yellow",
        ),
    )
    tbl.add_row(
        "Candidate Discovery",
        Text(
            status_emoji(ts.candidates_found),
            style="green" if ts.candidates_found else "yellow",
        ),
    )
    tbl.add_row(
        "Transcripts Ready",
        Text(
            status_emoji(ts.transcripts_ready),
            style="green" if ts.transcripts_ready else "yellow",
        ),
    )
    running = ts.classification_running and not ts.classification_done
    cls_label = f"{processed}/{total}" if total else "0/0"
    tbl.add_row(
        f"Incident Classification  [dim]({cls_label})[/dim]",
        Text(
            status_emoji(ts.classification_done, running),
            style=(
                "yellow"
                if running
                else ("green" if ts.classification_done else "yellow")
            ),
        ),
    )
    commit_running = ts.committing_running and not ts.committing_done
    tbl.add_row(
        f"Batch Commits  [dim](batches: {batches_done})[/dim]",
        Text(
            status_emoji(ts.committing_done, commit_running),
            style=(
                "yellow"
                if commit_running
                else ("green" if ts.committing_done else "yellow")
            ),
        ),
    )
    tbl.add_row(
        "Summary",
        Text(
            status_emoji(ts.summary_written),
            style="green" if ts.summary_written else "yellow",
        ),
    )
    return Panel(tbl, title="Task Board", border_style="white")


# ----- Live Stats (with avg + recent3) -----
def build_stats_panel(
    elapsed_s: float,
    updated: int,
    skipped: int,
    failures: int,
    total: int,
    classified_count: int,
    total_class_time_s: float,
    recent3: deque[Tuple[int | str, Optional[str], float, Optional[str]]],
    hide_text: bool,
    snippet_len: int,
) -> Panel:
    stats = Table.grid(padding=(0, 1), expand=True)
    stats.add_column(justify="left")
    stats.add_column(justify="right")
    processed = updated + skipped + failures
    throughput = processed / elapsed_s if elapsed_s > 0 else 0.0
    pending = max(total - processed, 0)
    stats.add_row("Elapsed", f"{timedelta(seconds=int(elapsed_s))}")
    stats.add_row("Throughput", f"{throughput:.1f} rows/sec")
    stats.add_row("Updated", f"[green]{updated}[/green]")
    stats.add_row("Skipped", f"{skipped}")
    stats.add_row("Failures", f"[red]{failures}[/red]")
    stats.add_row("Pending", f"{pending}")

    if classified_count > 0:
        avg_ms = (total_class_time_s / classified_count) * 1000.0
        stats.add_row("Avg classify time", f"{avg_ms:.1f} ms")
        # Most recent first
        for idx, (rid, pred, t_ms, snip) in enumerate(list(recent3)[::-1], 1):
            if hide_text:
                stats.add_row(
                    f"#{idx} recent", f"{rid}: {pred if pred else '—'} ({t_ms:.1f} ms)"
                )
            else:
                stats.add_row(
                    f"#{idx} recent",
                    f"{rid}: {pred if pred else '—'} ({t_ms:.1f} ms)\n[dim]{truncate(snip or '', snippet_len)}[/dim]",
                )

    return Panel(stats, title="Live Stats", border_style="blue", box=box.SQUARE)


# ----- Activity Feed -----
def build_activity_panel(feed: deque[str]) -> Panel:
    body = "[dim]Waiting for activity…[/dim]" if not feed else "\n".join(feed)
    return Panel(body, title="Activity Feed", border_style="magenta")


# ----- Current Transcript -----
def build_current_panel(
    current_id, current_pred, current_text, hide_text: bool, snippet_len: int
) -> Panel:
    if hide_text:
        body = f"[bold]id:[/bold] {current_id}   [bold]pred:[/bold] {current_pred if current_pred else '…'}"
    else:
        body = (
            f"[bold]id:[/bold] {current_id}   [bold]pred:[/bold] {current_pred if current_pred else '…'}\n"
            f"[dim]{truncate(current_text or '', snippet_len)}[/dim]"
        )
    return Panel(body, title="Now Processing", border_style="cyan")


# =======================
# Modes
# =======================
def render_layout(
    progress: Progress,
    tstate: TaskState,
    start: float,
    updated: int,
    skipped_same: int,
    failures: int,
    total_candidates: int,
    batches_done: int,
    activity: deque[str],
    classified_count: int,
    total_class_time_s: float,
    recent3: deque[Tuple[int | str, Optional[str], float, Optional[str]]],
    current_id,
    current_pred,
    current_text,
    hide_text: bool,
    snippet_len: int,
) -> RenderableType:
    elapsed = time.perf_counter() - start
    left = Panel(progress, title="Progress", border_style="cyan")
    right_col = [
        build_task_board(
            tstate, updated + skipped_same + failures, total_candidates, batches_done
        ),
        build_stats_panel(
            elapsed,
            updated,
            skipped_same,
            failures,
            total_candidates,
            classified_count,
            total_class_time_s,
            recent3,
            hide_text,
            snippet_len,
        ),
        build_current_panel(
            current_id, current_pred, current_text, hide_text, snippet_len
        ),
        build_activity_panel(activity),
    ]
    right = Columns(right_col, expand=True, equal=True)
    return Columns([left, right], expand=True, equal=True)


def run_live(
    progress: Progress,
    classification_task_id: int,
    rows: List[sqlite3.Row],
    action_fn,
    tstate: TaskState,
    start: float,
    updated_ref,
    skipped_ref,
    fail_ref,
    total_candidates: int,
    batches_done_ref,
    activity: deque[str],
    log_every: int,
    verbose_rows: bool,
    classified_count_ref,
    total_class_time_s_ref,
    recent3: deque,
    current_id_ref,
    current_pred_ref,
    current_text_ref,
    hide_text: bool,
    snippet_len: int,
):
    """Rich Live mode."""
    with Live(
        render_layout(
            progress,
            tstate,
            start,
            updated_ref[0],
            skipped_ref[0],
            fail_ref[0],
            total_candidates,
            batches_done_ref[0],
            activity,
            classified_count_ref[0],
            total_class_time_s_ref[0],
            recent3,
            current_id_ref[0],
            current_pred_ref[0],
            current_text_ref[0],
            hide_text,
            snippet_len,
        ),
        refresh_per_second=10,
        transient=True,
        screen=True,
        console=console,
    ) as live:
        progress.start()
        try:
            for i, r in enumerate(rows, start=1):
                current_id_ref[0] = r["id"]
                current_text_ref[0] = (r["transcript"] or "").strip()
                current_pred_ref[0] = None

                ok, changed, sample_tuple, predicted, elapsed_ms, snip = action_fn(r)
                current_pred_ref[0] = predicted

                classified_count_ref[0] += 1
                total_class_time_s_ref[0] += elapsed_ms / 1000.0
                recent3.append((r["id"], predicted, elapsed_ms, snip))

                if ok:
                    if changed:
                        updated_ref[0] += 1
                        if verbose_rows and (i % log_every == 0):
                            activity.append(f"✓ id={r['id']} → {predicted}")
                    else:
                        skipped_ref[0] += 1
                        if verbose_rows and (i % log_every == 0):
                            activity.append(f"• id={r['id']} unchanged")
                else:
                    fail_ref[0] += 1
                    if i % log_every == 0:
                        activity.append(f"⚠️ id={r['id']} failed")

                progress.advance(classification_task_id)
                if i % log_every == 0:
                    processed = updated_ref[0] + skipped_ref[0] + fail_ref[0]
                    activity.append(
                        f"⏱ Processed {processed}/{len(rows)} "
                        f"(upd {updated_ref[0]} / skip {skipped_ref[0]} / fail {fail_ref[0]})"
                    )

                live.update(
                    render_layout(
                        progress,
                        tstate,
                        start,
                        updated_ref[0],
                        skipped_ref[0],
                        fail_ref[0],
                        total_candidates,
                        batches_done_ref[0],
                        activity,
                        classified_count_ref[0],
                        total_class_time_s_ref[0],
                        recent3,
                        current_id_ref[0],
                        current_pred_ref[0],
                        current_text_ref[0],
                        hide_text,
                        snippet_len,
                    )
                )
        finally:
            progress.stop()


def run_soft_live(
    progress: Progress,
    classification_task_id: int,
    rows: List[sqlite3.Row],
    action_fn,
    tstate: TaskState,
    start: float,
    updated_ref,
    skipped_ref,
    fail_ref,
    total_candidates: int,
    batches_done_ref,
    activity: deque[str],
    log_every: int,
    verbose_rows: bool,
    fps: float,
    classified_count_ref,
    total_class_time_s_ref,
    recent3: deque,
    current_id_ref,
    current_pred_ref,
    current_text_ref,
    hide_text: bool,
    snippet_len: int,
):
    """Manual redraw loop (no Live)."""
    period = 1.0 / max(fps, 1.0)
    next_redraw = time.perf_counter()
    progress.start()
    try:
        for i, r in enumerate(rows, start=1):
            current_id_ref[0] = r["id"]
            current_text_ref[0] = (r["transcript"] or "").strip()
            current_pred_ref[0] = None

            ok, changed, sample_tuple, predicted, elapsed_ms, snip = action_fn(r)
            current_pred_ref[0] = predicted

            classified_count_ref[0] += 1
            total_class_time_s_ref[0] += elapsed_ms / 1000.0
            recent3.append((r["id"], predicted, elapsed_ms, snip))

            if ok:
                if changed:
                    updated_ref[0] += 1
                    if verbose_rows and (i % log_every == 0):
                        activity.append(f"✓ id={r['id']} → {predicted}")
                else:
                    skipped_ref[0] += 1
                    if verbose_rows and (i % log_every == 0):
                        activity.append(f"• id={r['id']} unchanged")
            else:
                fail_ref[0] += 1
                if i % log_every == 0:
                    activity.append(f"⚠️ id={r['id']} failed")

            progress.update(classification_task_id, completed=i)

            if i % log_every == 0:
                processed = updated_ref[0] + skipped_ref[0] + fail_ref[0]
                activity.append(
                    f"⏱ Processed {processed}/{len(rows)} "
                    f"(upd {updated_ref[0]} / skip {skipped_ref[0]} / fail {fail_ref[0]})"
                )

            now = time.perf_counter()
            if now >= next_redraw:
                console.clear()
                console.print(
                    render_layout(
                        progress,
                        tstate,
                        start,
                        updated_ref[0],
                        skipped_ref[0],
                        fail_ref[0],
                        total_candidates,
                        batches_done_ref[0],
                        activity,
                        classified_count_ref[0],
                        total_class_time_s_ref[0],
                        recent3,
                        current_id_ref[0],
                        current_pred_ref[0],
                        current_text_ref[0],
                        hide_text,
                        snippet_len,
                    )
                )
                next_redraw = now + period

        # final redraw
        console.clear()
        console.print(
            render_layout(
                progress,
                tstate,
                start,
                updated_ref[0],
                skipped_ref[0],
                fail_ref[0],
                total_candidates,
                batches_done_ref[0],
                activity,
                classified_count_ref[0],
                total_class_time_s_ref[0],
                recent3,
                current_id_ref[0],
                current_pred_ref[0],
                current_text_ref[0],
                hide_text,
                snippet_len,
            )
        )
    finally:
        progress.stop()


def run_plain(
    progress: Progress,
    classification_task_id: int,
    rows: List[sqlite3.Row],
    action_fn,
    log_every: int,
    hide_text: bool,
    snippet_len: int,
):
    progress.start()
    try:
        for i, r in enumerate(rows, start=1):
            ok, changed, sample_tuple, predicted, elapsed_ms, snip = action_fn(r)
            progress.update(classification_task_id, completed=i)
            if i % log_every == 0:
                base = f"[dim]Processed {i}/{len(rows)}"
                if not hide_text:
                    base += f"  |  {r['id']} → {predicted} ({elapsed_ms:.1f} ms): {truncate((r['transcript'] or '').strip(), snippet_len)}"
                console.print(base + "[/dim]")
    finally:
        progress.stop()


# =======================
# Main
# =======================
def main():
    global console
    args = build_args().parse_args()

    console = (
        Console(force_terminal=True, color_system="truecolor", soft_wrap=False)
        if args.force_live
        else Console(soft_wrap=False)
    )

    db_path = Path(args.db)
    if not db_path.exists():
        console.print(f"[red]Database not found:[/red] {db_path}")
        raise SystemExit(1)

    console.print(build_header_panel(db_path, args.table, args.batch, args.dry_run))

    start = time.perf_counter()
    total_candidates = 0
    rows: List[sqlite3.Row] = []

    # Task state & activity
    tstate = TaskState()
    activity = deque(maxlen=12)

    # Counters & metrics
    updated = 0
    skipped_same = 0
    failures = 0
    example_samples: List[Tuple[int | str, str, str]] = []
    last_commit = 0
    batches_done = 0

    classified_count = 0
    total_class_time_s = 0.0
    recent3: deque[Tuple[int | str, Optional[str], float, Optional[str]]] = deque(
        maxlen=3
    )

    # Live "current" refs
    current_id_ref = [None]
    current_pred_ref = [None]
    current_text_ref = [""]

    # Progress object (shared across modes)
    progress = Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.0f}%",
        "•",
        "Processed:",
        "{task.completed}/{task.total}",
        "•",
        TimeElapsedColumn(),
        "•",
        TimeRemainingColumn(),
        expand=True,
        console=console,
    )
    classification_task_id = None

    try:
        with sqlite_connect(db_path) as conn:
            tstate.db_connected = True
            activity.append("✅ Connected to database.")
            pre_n = count_candidates(
                conn, args.table, args.transcript_col, args.incident_col
            )
            console.print(build_candidates_panel(pre_n))

            total_candidates = pre_n
            tstate.candidates_found = True
            activity.append(f"🔎 Discovered {total_candidates} candidate rows.")

            if total_candidates == 0:
                console.print("[green]Nothing to do. Exiting.[/green]")
                return

            rows = fetch_candidates(
                conn,
                args.table,
                args.id_col,
                args.transcript_col,
                args.incident_col,
                limit=None if not args.max_updates else args.max_updates,
            )
            tstate.transcripts_ready = True
            activity.append(
                f"📝 Transcripts ready for classification (loaded {len(rows)} rows)."
            )

            classification_task_id = progress.add_task(
                "Incident Classification", total=len(rows)
            )
            tstate.classification_running = True

            # mutation-closed over locals
            updated_ref = [updated]
            skipped_ref = [skipped_same]
            fail_ref = [failures]
            batches_done_ref = [batches_done]
            classified_count_ref = [classified_count]
            total_class_time_s_ref = [total_class_time_s]

            def action_fn(r: sqlite3.Row):
                """Per-row handler.
                Returns (ok, changed, sample_tuple_or_None, predicted_label_or_none, elapsed_ms, snippet)
                """
                nonlocal last_commit
                row_id = r["id"]
                transcript = (r["transcript"] or "").strip()
                old = r["incident_type"]
                try:
                    t0 = time.perf_counter()
                    predicted = classify_incident(transcript)
                    t1 = time.perf_counter()
                    elapsed_ms = (t1 - t0) * 1000.0
                    snippet = transcript  # full, will be truncated in renderers

                    if not predicted or predicted == old:
                        return True, False, None, predicted, elapsed_ms, snippet

                    if not args.dry_run:
                        update_incident(
                            conn,
                            args.table,
                            args.incident_col,
                            args.id_col,
                            predicted,
                            row_id,
                        )
                        last_commit += 1
                        if last_commit >= args.batch:
                            tstate.committing_running = True
                            conn.commit()
                            last_commit = 0
                            batches_done_ref[0] += 1
                            activity.append(
                                f"💾 Committed batch #{batches_done_ref[0]}."
                            )

                    sample_tuple = (row_id, predicted, transcript)
                    if args.sample and len(example_samples) < args.sample:
                        example_samples.append(sample_tuple)
                    return True, True, sample_tuple, predicted, elapsed_ms, snippet

                except Exception:
                    return False, False, None, None, 0.0, None

            # Decide display mode
            use_live = (not args.no_live) and (args.force_live or sys.stdout.isatty())

            if use_live:
                try:
                    run_live(
                        progress,
                        classification_task_id,
                        rows,
                        action_fn,
                        tstate,
                        start,
                        updated_ref,
                        skipped_ref,
                        fail_ref,
                        total_candidates,
                        batches_done_ref,
                        activity,
                        args.log_every,
                        args.verbose_rows,
                        classified_count_ref,
                        total_class_time_s_ref,
                        recent3,
                        current_id_ref,
                        current_pred_ref,
                        current_text_ref,
                        args.no_transcript,
                        args.snippet_len,
                    )
                except LiveError:
                    console.print(
                        "[yellow]Live display unavailable, switching to Soft Live…[/yellow]"
                    )
                    run_soft_live(
                        progress,
                        classification_task_id,
                        rows,
                        action_fn,
                        tstate,
                        start,
                        updated_ref,
                        skipped_ref,
                        fail_ref,
                        total_candidates,
                        batches_done_ref,
                        activity,
                        args.log_every,
                        args.verbose_rows,
                        args.soft_live_rate,
                        classified_count_ref,
                        total_class_time_s_ref,
                        recent3,
                        current_id_ref,
                        current_pred_ref,
                        current_text_ref,
                        args.no_transcript,
                        args.snippet_len,
                    )
            else:
                run_plain(
                    progress,
                    classification_task_id,
                    rows,
                    action_fn,
                    args.log_every,
                    args.no_transcript,
                    args.snippet_len,
                )

            # Final commit if needed
            if not args.dry_run and last_commit > 0:
                tstate.committing_running = True
                conn.commit()
                last_commit = 0
                batches_done_ref[0] += 1
                activity.append(f"💾 Committed final batch #{batches_done_ref[0]}.")

            tstate.committing_running = False
            tstate.committing_done = True
            tstate.classification_running = False
            tstate.classification_done = True

            # Update locals from refs
            updated = updated_ref[0]
            skipped_same = skipped_ref[0]
            failures = fail_ref[0]
            batches_done = batches_done_ref[0]
            classified_count = classified_count_ref[0]
            total_class_time_s = total_class_time_s_ref[0]

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        try:
            if "conn" in locals() and not args.dry_run and last_commit > 0:
                conn.commit()
                console.print("[yellow]Committed a pending batch before exit.[/yellow]")
        except Exception:
            pass

    # Summary
    elapsed = time.perf_counter() - start
    processed_total = updated + skipped_same + failures
    rps = processed_total / elapsed if elapsed > 0 else 0.0
    tstate.summary_written = True

    summary = Table(title="Run Summary", box=box.SIMPLE_HEAVY, expand=True)
    summary.add_column("Metric", style="bold", no_wrap=True)
    summary.add_column("Value", justify="right")
    summary.add_row("Total candidates", f"{total_candidates}")
    summary.add_row("Processed this run", f"{processed_total}")
    summary.add_row("Updated", f"[green]{updated}[/green]")
    summary.add_row("Skipped (no change)", f"{skipped_same}")
    summary.add_row("Failures", f"[red]{failures}[/red]")
    summary.add_row("Elapsed", str(timedelta(seconds=int(elapsed))))
    summary.add_row("Throughput", f"{rps:.1f} rows/sec")
    if classified_count > 0:
        avg_ms = (total_class_time_s / classified_count) * 1000.0
        summary.add_row("Avg classify time", f"{avg_ms:.1f} ms")
    summary.add_row("Commit batches", f"{batches_done}")
    summary.add_row("Dry run", str(args.dry_run))

    console.print(Panel(Align.center(summary), border_style="green"))

    if example_samples:
        console.print(
            build_sample_table(example_samples, args.snippet_len, args.no_transcript)
        )

    console.print(
        Panel.fit(
            "[bold]Done.[/bold] "
            + (
                "[yellow]No changes written (dry run).[/yellow]"
                if args.dry_run
                else "[green]Changes committed.[/green]"
            ),
            border_style="cyan",
        )
    )


if __name__ == "__main__":
    main()
