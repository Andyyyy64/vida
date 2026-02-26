from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from life.config import Config

console = Console()


def _setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@click.group()
@click.option("-c", "--config", "config_path", type=click.Path(exists=False), default=None)
@click.option("-v", "--verbose", is_flag=True)
@click.pass_context
def cli(ctx, config_path: str | None, verbose: bool):
    """life.ai - Personal Life Observer (powered by Claude Code)"""
    _setup_logging(verbose)
    cfg_path = Path(config_path) if config_path else None
    ctx.ensure_object(dict)
    ctx.obj["config"] = Config.load(cfg_path)


@cli.command()
@click.option("-d", "--daemon", "background", is_flag=True, help="Run in background")
@click.pass_context
def start(ctx, background: bool):
    """Start the life observer daemon."""
    config: Config = ctx.obj["config"]

    if config.pid_file.exists():
        pid = config.pid_file.read_text().strip()
        try:
            os.kill(int(pid), 0)
            console.print(f"[yellow]Daemon already running (PID {pid})[/yellow]")
            return
        except (OSError, ValueError):
            config.pid_file.unlink()

    if background:
        proc = subprocess.Popen(
            [sys.executable, "-m", "life", "start"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        console.print(f"[green]Daemon started in background (PID {proc.pid})[/green]")
    else:
        console.print("[green]Starting life observer (Claude Code watching)...[/green]")
        from life.daemon import Daemon
        daemon = Daemon(config)
        daemon.run()


@cli.command()
@click.pass_context
def stop(ctx):
    """Stop the running daemon."""
    config: Config = ctx.obj["config"]

    if not config.pid_file.exists():
        console.print("[yellow]No running daemon found[/yellow]")
        return

    pid_str = config.pid_file.read_text().strip()
    try:
        pid = int(pid_str)
        os.kill(pid, signal.SIGTERM)
        console.print(f"[green]Sent stop signal to daemon (PID {pid})[/green]")
    except (ValueError, OSError) as e:
        console.print(f"[red]Failed to stop daemon: {e}[/red]")
        config.pid_file.unlink(missing_ok=True)


@cli.command()
@click.pass_context
def status(ctx):
    """Show daemon status and statistics."""
    config: Config = ctx.obj["config"]

    running = False
    pid = None
    if config.pid_file.exists():
        pid_str = config.pid_file.read_text().strip()
        try:
            pid = int(pid_str)
            os.kill(pid, 0)
            running = True
        except (ValueError, OSError):
            pass

    if running:
        console.print(f"[green]● Daemon running[/green] (PID {pid})")
    else:
        console.print("[red]● Daemon stopped[/red]")

    from life.capture.frame_store import FrameStore
    from life.capture.screen import ScreenCapture
    from life.capture.audio import AudioCapture
    store = FrameStore(config.data_dir)
    screen_store = ScreenCapture(config.data_dir)
    audio_store = AudioCapture(config.data_dir)
    frames_today = store.get_frame_count_today()
    disk = store.get_disk_usage() + screen_store.get_disk_usage() + audio_store.get_disk_usage()
    disk_mb = disk / (1024 * 1024)

    from life.storage.database import Database
    if config.db_path.exists():
        db = Database(config.db_path)
        db_frames = db.get_frame_count_for_date(date.today())
        summaries = db.get_summaries_for_date(date.today())
        latest = db.get_latest_frame()
        db.close()
    else:
        db_frames = 0
        summaries = []
        latest = None

    console.print(f"  Frames today: {frames_today} (DB: {db_frames})")
    console.print(f"  Summaries:    {len(summaries)}")
    console.print(f"  Disk usage:   {disk_mb:.1f} MB")
    console.print(f"  Data dir:     {config.data_dir.resolve()}")

    if latest and latest.claude_description:
        console.print(f"  Latest:       {latest.claude_description[:80]}")


@cli.command()
@click.pass_context
def capture(ctx):
    """Capture a single test frame."""
    config: Config = ctx.obj["config"]

    from life.capture.camera import Camera
    from life.capture.frame_store import FrameStore

    camera = Camera(config.capture)
    if not camera.open():
        console.print("[red]Failed to open camera[/red]")
        return

    frame = camera.capture()
    camera.close()

    if frame is None:
        console.print("[red]Failed to capture frame[/red]")
        return

    store = FrameStore(config.data_dir, config.capture.jpeg_quality)
    path = store.save(frame)
    abs_path = config.data_dir / path
    console.print(f"[green]Captured:[/green] {abs_path}")
    console.print(f"  Size: {abs_path.stat().st_size / 1024:.1f} KB")
    console.print(f"  Resolution: {frame.shape[1]}x{frame.shape[0]}")


@cli.command()
@click.pass_context
def look(ctx):
    """Capture a frame and have Claude Code analyze it right now."""
    config: Config = ctx.obj["config"]

    from life.analyzer import FrameAnalyzer
    from life.capture.camera import Camera
    from life.capture.frame_store import FrameStore
    from life.capture.screen import ScreenCapture
    from life.llm import create_provider
    from life.storage.database import Database
    from life.storage.models import Frame
    from life.analysis.scene import SceneAnalyzer

    camera = Camera(config.capture)
    if not camera.open():
        console.print("[red]Failed to open camera[/red]")
        return

    raw = camera.capture()
    camera.close()

    if raw is None:
        console.print("[red]Failed to capture frame[/red]")
        return

    now = datetime.now()
    store = FrameStore(config.data_dir, config.capture.jpeg_quality)
    rel_path = store.save(raw, now)

    screen = ScreenCapture(config.data_dir)
    screen_path = screen.capture(now) or ""

    scene = SceneAnalyzer(config.analysis.brightness_dark, config.analysis.brightness_bright)
    brightness = scene.get_brightness(raw)

    frame = Frame(timestamp=now, path=rel_path, screen_path=screen_path, brightness=brightness)

    console.print(f"[green]Camera:[/green]  {config.data_dir / rel_path}")
    if screen_path:
        console.print(f"[green]Screen:[/green]  {config.data_dir / screen_path}")
    console.print(f"[dim]Analyzing...[/dim]")

    provider = create_provider(
        config.llm.provider,
        claude_model=config.llm.claude_model,
        gemini_model=config.llm.gemini_model,
    )
    db = Database(config.db_path)
    analyzer = FrameAnalyzer(provider, config.data_dir, db)
    description, activity = analyzer.analyze(frame)

    if description:
        label = f"[{activity}] " if activity else ""
        console.print(Panel(f"{label}{description}", title="Claude Code says", border_style="blue"))
        frame_id = db.insert_frame(frame)
        db.update_frame_analysis(frame_id, description, activity)
    else:
        console.print("[yellow]Claude Code could not analyze the frame[/yellow]")
    db.close()


@cli.command()
@click.option("-n", "--count", default=5, help="Number of recent frames")
@click.pass_context
def recent(ctx, count: int):
    """Show recent frame analyses by Claude Code."""
    config: Config = ctx.obj["config"]

    from life.storage.database import Database

    if not config.db_path.exists():
        console.print("[dim]No data yet[/dim]")
        return

    db = Database(config.db_path)
    frames = db.get_frames_for_date(date.today())
    db.close()

    if not frames:
        console.print("[dim]No frames today[/dim]")
        return

    recent_frames = frames[-count:]

    table = Table(title=f"Recent Frames (last {len(recent_frames)})")
    table.add_column("Time", style="cyan")
    table.add_column("Motion", justify="right", style="yellow")
    table.add_column("Claude Analysis")

    for f in recent_frames:
        desc = f.claude_description or "[dim]pending[/dim]"
        if f.transcription:
            desc += f"\n[dim]🎤 {f.transcription[:60]}[/dim]"
        table.add_row(
            f.timestamp.strftime("%H:%M:%S"),
            f"{f.motion_score:.3f}",
            desc,
        )
    console.print(table)


@cli.command()
@click.argument("target_date", required=False)
@click.pass_context
def today(ctx, target_date: str | None):
    """Show today's timeline (events + summaries)."""
    config: Config = ctx.obj["config"]
    d = _parse_date(target_date) if target_date else date.today()

    from life.storage.database import Database
    from life.summary.formatter import SummaryFormatter
    from life.summary.timeline import TimelineBuilder

    if not config.db_path.exists():
        console.print("[dim]No data yet[/dim]")
        return

    db = Database(config.db_path)
    builder = TimelineBuilder(db)
    formatter = SummaryFormatter(builder)
    formatter.print_timeline(d)
    db.close()


@cli.command()
@click.argument("target_date", required=False)
@click.pass_context
def stats(ctx, target_date: str | None):
    """Show daily statistics."""
    config: Config = ctx.obj["config"]
    d = _parse_date(target_date) if target_date else date.today()

    from life.storage.database import Database
    from life.summary.formatter import SummaryFormatter
    from life.summary.timeline import TimelineBuilder

    if not config.db_path.exists():
        console.print("[dim]No data yet[/dim]")
        return

    db = Database(config.db_path)
    builder = TimelineBuilder(db)
    formatter = SummaryFormatter(builder)
    formatter.print_stats(d)
    db.close()


@cli.command()
@click.argument("target_date", required=False)
@click.option("--scale", type=click.Choice(["10m", "30m", "1h", "6h", "12h", "24h"]), default=None)
@click.pass_context
def summaries(ctx, target_date: str | None, scale: str | None):
    """Show Claude-generated summaries."""
    config: Config = ctx.obj["config"]
    d = _parse_date(target_date) if target_date else date.today()

    from life.storage.database import Database

    if not config.db_path.exists():
        console.print("[dim]No data yet[/dim]")
        return

    db = Database(config.db_path)
    sums = db.get_summaries_for_date(d, scale)
    db.close()

    if not sums:
        console.print(f"[dim]No summaries for {d.isoformat()}{f' ({scale})' if scale else ''}[/dim]")
        return

    for s in sums:
        console.print(Panel(
            s.content,
            title=f"{s.timestamp.strftime('%H:%M')} [{s.scale}] ({s.frame_count} frames)",
            border_style="blue" if s.scale in ("1h", "6h", "12h", "24h") else "dim",
        ))


@cli.command()
@click.argument("target_date", required=False)
@click.pass_context
def events(ctx, target_date: str | None):
    """Show events for the day."""
    config: Config = ctx.obj["config"]
    d = _parse_date(target_date) if target_date else date.today()

    from life.storage.database import Database

    if not config.db_path.exists():
        console.print("[dim]No data yet[/dim]")
        return

    db = Database(config.db_path)
    event_list = db.get_events_for_date(d)
    db.close()

    if not event_list:
        console.print(f"[dim]No events for {d.isoformat()}[/dim]")
        return

    table = Table(title=f"Events - {d.isoformat()}")
    table.add_column("Time", style="cyan")
    table.add_column("Type", style="bold")
    table.add_column("Description")

    for e in event_list:
        table.add_row(
            e.timestamp.strftime("%H:%M:%S"),
            e.event_type,
            e.description,
        )
    console.print(table)


@cli.command()
@click.argument("target_date", required=False)
@click.pass_context
def report(ctx, target_date: str | None):
    """Generate daily diary report."""
    config: Config = ctx.obj["config"]
    d = _parse_date(target_date) if target_date else date.today()

    from life.llm import create_provider
    from life.report import ReportGenerator
    from life.storage.database import Database

    if not config.db_path.exists():
        console.print("[dim]No data yet[/dim]")
        return

    provider = create_provider(
        config.llm.provider,
        claude_model=config.llm.claude_model,
        gemini_model=config.llm.gemini_model,
    )
    db = Database(config.db_path)
    gen = ReportGenerator(provider, db, config.data_dir)
    rpt = gen.generate(d)
    if rpt:
        console.print(Panel(rpt.content, title=f"Daily Report — {d.isoformat()}", border_style="blue"))
        console.print(f"[dim]{rpt.frame_count} frames, focus {rpt.focus_pct:.0f}%[/dim]")
    else:
        console.print(f"[yellow]Could not generate report for {d.isoformat()}[/yellow]")
    db.close()


@cli.command()
@click.argument("target_date", required=False)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
@click.pass_context
def review(ctx, target_date: str | None, as_json: bool):
    """Generate review package for Claude Code."""
    config: Config = ctx.obj["config"]
    d = _parse_date(target_date) if target_date else date.today()

    from life.claude.review import ReviewPackager
    from life.storage.database import Database

    if not config.db_path.exists():
        console.print("[dim]No data yet[/dim]")
        return

    db = Database(config.db_path)
    packager = ReviewPackager(config, db)

    if as_json:
        import json
        package = packager.generate(d)
        click.echo(json.dumps(package, indent=2, ensure_ascii=False))
    else:
        out_path = packager.save_review(d)
        prompt = packager.get_prompt(d)
        console.print(f"[green]Review package saved:[/green] {out_path}")
        console.print()
        console.print(Panel(prompt, title="Prompt for Claude Code", border_style="blue"))

    db.close()


@cli.command("notify-test")
@click.pass_context
def notify_test(ctx):
    """Send a test notification to verify webhook configuration."""
    config: Config = ctx.obj["config"]

    if not config.notify.enabled:
        console.print("[yellow]Notifications are not enabled.[/yellow]")
        console.print("Add to life.toml:")
        console.print("[dim]  [notify]")
        console.print("  enabled = true")
        console.print("  provider = \"discord\"  # or \"line\"")
        console.print("  webhook_url = \"https://discord.com/api/webhooks/...\"[/dim]")
        return

    from life.notify import send_notification

    console.print(f"[dim]Sending test to {config.notify.provider}...[/dim]")
    ok = send_notification(
        config.notify,
        "life.ai Test Notification",
        "This is a test message from life.ai. If you see this, notifications are working correctly!",
    )
    if ok:
        console.print("[green]Notification sent successfully![/green]")
    else:
        console.print("[red]Failed to send notification. Check logs and webhook_url.[/red]")


def _parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise click.BadParameter(f"Invalid date: {s} (expected YYYY-MM-DD)")
