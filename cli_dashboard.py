import time
import threading
import argparse
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from data import AudioMetadata
import api
from app import monitor_directory, GetPathForRecordingsToday

console = Console()
RUNNING = True
AI_OVERVIEW = "[grey]AI Overview not enabled.[/grey]"


def parse_args():
    parser = argparse.ArgumentParser(
        description="🚨 Local PD/FD Incident Dashboard CLI"
    )
    parser.add_argument(
        "-ai", "--ai-overview", action="store_true", help="Enable AI overview panel"
    )
    parser.add_argument(
        "-f",
        "--filter",
        choices=["police", "fire"],
        help="Filter by department at start",
    )
    parser.add_argument(
        "-r",
        "--refresh",
        type=int,
        default=1,
        help="Dashboard refresh interval in seconds (default: 1s)",
    )
    parser.add_argument(
        "-s",
        "--summary",
        action="store_true",
        help="Generate AI summary of recent incidents and exit",
    )
    parser.add_argument(
        "-d",
        "--date",
        type=str,
        help="View logs for specific date (MM-DD-YY), defaults to today",
    )
    return parser.parse_args()


def build_table(data_obj, dept_filter):
    data_obj.reload()
    data = data_obj.get_all()

    table = Table(title="🚨 Live PD/FD Incident Dashboard", expand=True)
    table.add_column("Time", style="cyan", no_wrap=True)
    table.add_column("Department", style="magenta")
    table.add_column("Transcript", style="white")

    entries = sorted(data.items(), key=lambda x: x[1].get("Time", "00:00:00"))

    for filename, info in entries:
        dept = "Unknown"
        if "Police" in filename:
            dept = "[blue]Police[/blue]"
        elif "Fire" in filename:
            dept = "[red]Fire[/red]"

        if dept_filter and dept_filter not in dept.lower():
            continue

        transcript_raw = info.get("Transcript", "")
        transcript = (
            transcript_raw.strip()
            if isinstance(transcript_raw, str)
            else "[italic grey]No transcript[/italic grey]"
        )

        if not transcript:
            transcript = "[italic grey]No transcript[/italic grey]"

        table.add_row(info.get("Time", "N/A"), dept, transcript)

    return table


def cli_input_listener():
    global RUNNING
    while RUNNING:
        cmd = console.input("[bold green]Command>[/] ").strip().lower()
        if cmd == "exit":
            RUNNING = False
        else:
            console.print("[yellow]Unknown command.[/] Available: exit")


def ai_overview_updater(data_obj, interval):
    global AI_OVERVIEW
    while RUNNING:
        try:
            data_obj.reload()
            data = data_obj.get_all()
            transcripts = [
                info["Transcript"] for info in data.values() if info.get("Transcript")
            ]
            recent_transcripts = "\n".join(transcripts[-30:])

            if recent_transcripts.strip():
                AI_OVERVIEW = api.LLM_REQ(
                    f"Summarize these recent police and fire department incidents:\n{recent_transcripts}"
                )
            else:
                AI_OVERVIEW = "[grey]No incidents to summarize yet...[/grey]"

        except Exception as e:
            AI_OVERVIEW = f"[red]Error generating overview: {e}[/red]"

        time.sleep(interval)


def generate_one_time_summary(data_obj):
    data_obj.reload()
    data = data_obj.get_all()
    transcripts = [
        info["Transcript"] for info in data.values() if info.get("Transcript")
    ]
    recent_transcripts = "\n".join(transcripts[-50:])
    if recent_transcripts.strip():
        summary = api.LLM_REQ(
            f"Summarize these recent police and fire department incidents:\n{recent_transcripts}"
        )
        console.print(Panel(summary, title="🧠 AI Summary"))
    else:
        console.print("[grey]No incidents available to summarize.[/grey]")


def main():
    args = parse_args()

    # Handle custom date
    if args.date:
        date_str = args.date.replace("-", "-")
        path = f"C:/ProScan/Recordings/{date_str}/Middlesex/"
        Data = AudioMetadata()  # Would need to adjust to load old logs
    else:
        path = GetPathForRecordingsToday()
        Data = AudioMetadata()

    if args.summary:
        generate_one_time_summary(Data)
        return

    threading.Thread(target=monitor_directory, args=(path,), daemon=True).start()
    threading.Thread(target=cli_input_listener, daemon=True).start()

    if args.ai_overview:
        threading.Thread(
            target=ai_overview_updater, args=(Data, 300), daemon=True
        ).start()

    with Live(refresh_per_second=args.refresh, screen=True) as live:
        while RUNNING:
            dashboard = Table.grid(expand=True)
            dashboard.add_row(build_table(Data, args.filter))
            if args.ai_overview:
                dashboard.add_row(
                    Panel(
                        AI_OVERVIEW,
                        title="🧠 AI Overview (updates every 5 min)",
                        border_style="green",
                    )
                )

            live.update(dashboard)
            time.sleep(args.refresh)

    console.print("[bold red]Exiting dashboard...[/bold red]")


if __name__ == "__main__":
    main()
