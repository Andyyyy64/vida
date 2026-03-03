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

from daemon.config import Config

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
    """homelife.ai - Personal Life Observer (powered by homelife.ai)"""
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
            [sys.executable, "-m", "daemon", "start"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        console.print(f"[green]Daemon started in background (PID {proc.pid})[/green]")
    else:
        console.print("[green]Starting life observer (homelife.ai watching)...[/green]")
        from daemon.daemon import Daemon
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

    from daemon.capture.frame_store import FrameStore
    from daemon.capture.screen import ScreenCapture
    from daemon.capture.audio import AudioCapture
    store = FrameStore(config.data_dir)
    screen_store = ScreenCapture(config.data_dir)
    audio_store = AudioCapture(config.data_dir)
    frames_today = store.get_frame_count_today()
    disk = store.get_disk_usage() + screen_store.get_disk_usage() + audio_store.get_disk_usage()
    disk_mb = disk / (1024 * 1024)

    from daemon.storage.database import Database
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

    from daemon.capture.camera import Camera
    from daemon.capture.frame_store import FrameStore

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
    """Capture a frame and have homelife.ai analyze it right now."""
    config: Config = ctx.obj["config"]

    from daemon.analyzer import FrameAnalyzer
    from daemon.capture.camera import Camera
    from daemon.capture.frame_store import FrameStore
    from daemon.capture.screen import ScreenCapture
    from daemon.llm import create_provider
    from daemon.storage.database import Database
    from daemon.storage.models import Frame
    from daemon.analysis.scene import SceneAnalyzer

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
    from daemon.activity import ActivityManager
    activity_mgr = ActivityManager(db)
    analyzer = FrameAnalyzer(provider, config.data_dir, db, activity_mgr)
    description, activity = analyzer.analyze(frame)

    if description:
        label = f"[{activity}] " if activity else ""
        console.print(Panel(f"{label}{description}", title="homelife.ai says", border_style="blue"))
        frame_id = db.insert_frame(frame)
        db.update_frame_analysis(frame_id, description, activity)
    else:
        console.print("[yellow]homelife.ai could not analyze the frame[/yellow]")
    db.close()


@cli.command()
@click.option("-n", "--count", default=5, help="Number of recent frames")
@click.pass_context
def recent(ctx, count: int):
    """Show recent frame analyses by homelife.ai."""
    config: Config = ctx.obj["config"]

    from daemon.storage.database import Database

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

    from daemon.storage.database import Database
    from daemon.summary.formatter import SummaryFormatter
    from daemon.summary.timeline import TimelineBuilder

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

    from daemon.storage.database import Database
    from daemon.summary.formatter import SummaryFormatter
    from daemon.summary.timeline import TimelineBuilder

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

    from daemon.storage.database import Database

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

    from daemon.storage.database import Database

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

    from daemon.llm import create_provider
    from daemon.report import ReportGenerator
    from daemon.storage.database import Database

    if not config.db_path.exists():
        console.print("[dim]No data yet[/dim]")
        return

    provider = create_provider(
        config.llm.provider,
        claude_model=config.llm.claude_model,
        gemini_model=config.llm.gemini_model,
    )
    db = Database(config.db_path)
    from daemon.activity import ActivityManager
    activity_mgr = ActivityManager(db)
    gen = ReportGenerator(provider, db, config.data_dir, activity_mgr)
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
    """Generate review package for homelife.ai."""
    config: Config = ctx.obj["config"]
    d = _parse_date(target_date) if target_date else date.today()

    from daemon.claude.review import ReviewPackager
    from daemon.storage.database import Database

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
        console.print(Panel(prompt, title="Prompt for homelife.ai", border_style="blue"))

    db.close()


@cli.command("notify-test")
@click.pass_context
def notify_test(ctx):
    """Send a test notification to verify webhook configuration."""
    config: Config = ctx.obj["config"]

    if not config.notify.enabled:
        console.print("[yellow]Notifications are not enabled.[/yellow]")
        console.print("Add to life.toml:")
        console.print("[dim]  \\[notify]\n  enabled = true\n  provider = \"discord\"  # or \"line\"\n  webhook_url = \"https://discord.com/api/webhooks/...\"[/dim]")
        return

    from daemon.notify import send_notification

    console.print(f"[dim]Sending test to {config.notify.provider}...[/dim]")
    ok = send_notification(
        config.notify,
        "homelife.ai Test Notification",
        "This is a test message from daemon.ai. If you see this, notifications are working correctly!",
    )
    if ok:
        console.print("[green]Notification sent successfully![/green]")
    else:
        console.print("[red]Failed to send notification. Check logs and webhook_url.[/red]")


@cli.command()
@click.option("--regen", is_flag=True, help="Regenerate knowledge profile")
@click.pass_context
def knowledge(ctx, regen: bool):
    """Show or regenerate the knowledge profile."""
    config: Config = ctx.obj["config"]

    from daemon.storage.database import Database

    if not config.db_path.exists():
        console.print("[dim]No data yet[/dim]")
        return

    db = Database(config.db_path)

    if regen:
        from daemon.knowledge import KnowledgeGenerator
        from daemon.llm import create_provider

        provider = create_provider(
            config.llm.provider,
            claude_model=config.llm.claude_model,
            gemini_model=config.llm.gemini_model,
        )
        gen = KnowledgeGenerator(provider, db, config.data_dir)
        console.print("[dim]Generating knowledge profile...[/dim]")
        content = gen.generate()
        if content:
            console.print(Panel(content, title="Knowledge Profile (regenerated)", border_style="green"))
        else:
            console.print("[yellow]Could not generate knowledge profile (no data or LLM failure)[/yellow]")
    else:
        content = db.get_latest_knowledge()
        if content:
            last_time = db.get_latest_knowledge_time()
            ts = last_time.strftime("%Y-%m-%d %H:%M") if last_time else "unknown"
            console.print(Panel(content, title=f"Knowledge Profile (generated: {ts})", border_style="blue"))
        else:
            console.print("[dim]No knowledge profile yet. Run with --regen to generate.[/dim]")

    db.close()


@cli.command("consolidate-activities")
@click.option("--dry-run", is_flag=True, help="Show suggestions without applying changes")
@click.pass_context
def consolidate_activities(ctx, dry_run: bool):
    """Use LLM to merge duplicate/similar activity categories."""
    import json

    config: Config = ctx.obj["config"]

    if not config.db_path.exists():
        console.print("[dim]No data yet[/dim]")
        return

    from daemon.activity import ActivityManager
    from daemon.llm import create_provider
    from daemon.storage.database import Database

    db = Database(config.db_path)
    activity_mgr = ActivityManager(db)
    mappings = db.get_all_activity_mappings()

    if len(mappings) < 2:
        console.print("[dim]Not enough activity categories to consolidate[/dim]")
        db.close()
        return

    console.print(f"[dim]Found {len(mappings)} activity categories. Asking LLM for consolidation suggestions...[/dim]")

    acts_lines = [
        f"- {r['activity']} [{r['meta_category']}] ({r['frame_count']}フレーム)"
        for r in mappings
    ]
    prompt = (
        "以下は記録されたアクティビティカテゴリの一覧です（カウントは記録フレーム数）:\n\n"
        + "\n".join(acts_lines)
        + "\n\n"
        "同じ行動を指している異なる表現を統合したいです。以下の基準でマージ候補を返してください:\n"
        "- 類義語（例: プログラミング / コーディング / ソフトウェア開発 → プログラミング）\n"
        "- 表記ゆれ（例: YouTubeを見る / YouTube視聴 → YouTube視聴）\n"
        "- 詳細度の違いで本質的に同じ（例: プログラミング作業 / プログラミング → プログラミング）\n\n"
        "マージすべきペアのみを以下のJSON形式で出力してください（不要なものは含めない）:\n"
        '[{"from": "古い名前", "to": "統合先の代表名", "reason": "理由（日本語）"}]\n'
        "ルール:\n"
        "- 'to' は既存カテゴリ名から選ぶこと（フレーム数が多い方を代表名に）\n"
        "- 意味が明確に異なるものはマージしない\n"
        "- JSONのみを出力すること\n"
    )

    provider = create_provider(
        config.llm.provider,
        claude_model=config.llm.claude_model,
        gemini_model=config.llm.gemini_model,
    )
    raw = provider.generate_text(prompt) or ""
    raw = raw.strip()

    start = raw.find("[")
    end = raw.rfind("]") + 1
    suggestions: list[tuple[str, str, str]] = []
    if start >= 0 and end > start:
        try:
            pairs = json.loads(raw[start:end])
            for p in pairs:
                if isinstance(p, dict) and "from" in p and "to" in p:
                    suggestions.append((p["from"], p["to"], p.get("reason", "")))
        except json.JSONDecodeError:
            pass

    if not suggestions:
        console.print("[green]No consolidations suggested — categories look clean![/green]")
        db.close()
        return

    table = Table(title="Suggested Activity Merges")
    table.add_column("#", style="dim", width=3)
    table.add_column("From", style="red")
    table.add_column("→ To", style="green")
    table.add_column("Reason", style="dim")
    for i, (from_act, to_act, reason) in enumerate(suggestions, 1):
        table.add_row(str(i), from_act, to_act, reason)
    console.print(table)

    if dry_run:
        console.print("[dim]Dry run — no changes applied[/dim]")
        db.close()
        return

    if not click.confirm(f"\nApply all {len(suggestions)} merges?"):
        db.close()
        return

    all_acts = {r["activity"] for r in db.get_all_activity_mappings()}
    applied = 0
    for from_act, to_act, _ in suggestions:
        if from_act not in all_acts:
            console.print(f"[yellow]Skip: '{from_act}' not in DB[/yellow]")
            continue
        if from_act == to_act:
            continue
        activity_mgr.apply_merge(from_act, to_act)
        all_acts.discard(from_act)
        all_acts.add(to_act)
        console.print(f"  [green]✓[/green] {from_act} → {to_act}")
        applied += 1

    console.print(f"\n[green]Applied {applied} merges.[/green]")
    db.close()


def _parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise click.BadParameter(f"Invalid date: {s} (expected YYYY-MM-DD)")
