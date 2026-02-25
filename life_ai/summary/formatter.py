from __future__ import annotations

from datetime import date

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from life_ai.summary.timeline import TimelineBuilder


class SummaryFormatter:
    def __init__(self, timeline_builder: TimelineBuilder):
        self._builder = timeline_builder
        self._console = Console()

    def print_timeline(self, d: date):
        entries = self._builder.build(d)
        if not entries:
            self._console.print(f"[dim]No data for {d.isoformat()}[/dim]")
            return

        table = Table(title=f"Timeline - {d.isoformat()}", show_lines=False)
        table.add_column("Time", style="cyan", width=6)
        table.add_column("", width=2)
        table.add_column("Description")

        for entry in entries:
            table.add_row(entry.time, entry.icon, entry.description)

        self._console.print(table)

    def print_stats(self, d: date):
        stats = self._builder.get_day_stats(d)

        table = Table(title=f"Stats - {stats['date']}")
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right")

        table.add_row("Total frames", str(stats["total_frames"]))
        table.add_row("Claude analyzed", str(stats["analyzed_frames"]))
        table.add_row("Events", str(stats["total_events"]))
        table.add_row("Avg brightness", f"{stats['avg_brightness']:.1f}")
        table.add_row("Avg motion", f"{stats['avg_motion']:.4f}")

        self._console.print(table)

        if stats["summary_counts"]:
            st = Table(title="Summaries Generated")
            st.add_column("Scale", style="bold")
            st.add_column("Count", justify="right")
            for scale, count in sorted(stats["summary_counts"].items()):
                st.add_row(scale, str(count))
            self._console.print(st)
