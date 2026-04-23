from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
from datetime import date, datetime
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
    """vida - Personal Life Observer (powered by vida)"""
    _setup_logging(verbose)
    ctx.ensure_object(dict)

    if config_path:
        # Explicit config file — use legacy file-based loading
        ctx.obj["config"] = Config.load(Path(config_path))
    else:
        # Prefer DB-based config (settings table in life.db)
        data_dir = Path(os.environ.get("DATA_DIR", "data"))
        db_path = data_dir / "life.db"
        if db_path.exists():
            ctx.obj["config"] = Config.load_from_db(db_path)
        else:
            ctx.obj["config"] = Config.load()


@cli.command()
@click.option("-d", "--daemon", "background", is_flag=True, help="Run in background")
@click.pass_context
def start(ctx, background: bool):
    """Start the life observer daemon."""
    config: Config = ctx.obj["config"]

    if config.pid_file.exists():
        pid_str = config.pid_file.read_text().strip()
        try:
            pid = int(pid_str)
            os.kill(pid, 0)  # raises OSError if process is gone
            # On Linux, check if the process is in stopped (T) state — if so, kill it
            stopped = False
            status_path = Path(f"/proc/{pid}/status")
            if status_path.exists():
                for line in status_path.read_text().splitlines():
                    if line.startswith("State:") and "\tT" in line:
                        stopped = True
                        break
            if stopped:
                os.kill(pid, signal.SIGKILL)
                config.pid_file.unlink()
                console.print(f"[yellow]Killed stopped daemon (PID {pid}), starting fresh...[/yellow]")
            else:
                console.print(f"[yellow]Daemon already running (PID {pid})[/yellow]")
                return
        except (OSError, ValueError):
            if config.pid_file.exists():
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
        console.print("[green]Starting life observer (vida watching)...[/green]")
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

    from daemon.capture.audio import AudioCapture
    from daemon.capture.frame_store import FrameStore
    from daemon.capture.screen import ScreenCapture

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
    """Capture a frame and have vida analyze it right now."""
    config: Config = ctx.obj["config"]

    from daemon.analysis.scene import SceneAnalyzer
    from daemon.analyzer import FrameAnalyzer
    from daemon.capture.camera import Camera
    from daemon.capture.frame_store import FrameStore
    from daemon.capture.screen import ScreenCapture
    from daemon.llm import create_provider
    from daemon.storage.database import Database
    from daemon.storage.models import Frame

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
    console.print("[dim]Analyzing...[/dim]")

    if config.llm.provider == "external":
        console.print(
            "[yellow]'look' requires a local LLM provider. Set llm.provider to 'claude', 'codex', or 'gemini'.[/yellow]"
        )
        return

    provider = create_provider(
        config.llm.provider,
        claude_model=config.llm.claude_model,
        codex_model=config.llm.codex_model,
        gemini_model=config.llm.gemini_model,
    )
    db = Database(config.db_path)
    from daemon.activity import ActivityManager

    activity_mgr = ActivityManager(db)
    analyzer = FrameAnalyzer(provider, config.data_dir, db, activity_mgr)
    description, activity = analyzer.analyze(frame)

    if description:
        label = f"[{activity}] " if activity else ""
        console.print(Panel(f"{label}{description}", title="vida says", border_style="blue"))
        frame_id = db.insert_frame(frame)
        db.update_frame_analysis(frame_id, description, activity)
    else:
        console.print("[yellow]vida could not analyze the frame[/yellow]")
    db.close()


@cli.command()
@click.option("-n", "--count", default=5, help="Number of recent frames")
@click.pass_context
def recent(ctx, count: int):
    """Show recent frame analyses by vida."""
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
        console.print(
            Panel(
                s.content,
                title=f"{s.timestamp.strftime('%H:%M')} [{s.scale}] ({s.frame_count} frames)",
                border_style="blue" if s.scale in ("1h", "6h", "12h", "24h") else "dim",
            )
        )


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

    if config.llm.provider == "external":
        console.print(
            "[yellow]'report' requires a local LLM provider. Set llm.provider to 'claude', 'codex', or 'gemini'.[/yellow]"
        )
        return

    provider = create_provider(
        config.llm.provider,
        claude_model=config.llm.claude_model,
        codex_model=config.llm.codex_model,
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
    """Generate review package for vida."""
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
        console.print(Panel(prompt, title="Prompt for vida", border_style="blue"))

    db.close()


@cli.command("notify-test")
@click.pass_context
def notify_test(ctx):
    """Send a test notification to verify webhook configuration."""
    config: Config = ctx.obj["config"]

    if not config.notify.enabled:
        console.print("[yellow]Notifications are not enabled.[/yellow]")
        console.print("Add to life.toml:")
        console.print(
            '[dim]  \\[notify]\n  enabled = true\n  provider = "discord"  # or "line"\n  webhook_url = "https://discord.com/api/webhooks/..."[/dim]'
        )
        return

    from daemon.notify import send_notification

    console.print(f"[dim]Sending test to {config.notify.provider}...[/dim]")
    ok = send_notification(
        config.notify,
        "vida Test Notification",
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
        if config.llm.provider == "external":
            console.print(
                "[yellow]'knowledge --regen' requires a local LLM provider. Set llm.provider to 'claude', 'codex', or 'gemini'.[/yellow]"
            )
            db.close()
            return

        from daemon.knowledge import KnowledgeGenerator
        from daemon.llm import create_provider

        provider = create_provider(
            config.llm.provider,
            claude_model=config.llm.claude_model,
            codex_model=config.llm.codex_model,
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

    acts_lines = [f"- {r['activity']} [{r['meta_category']}] ({r['frame_count']}フレーム)" for r in mappings]
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
        codex_model=config.llm.codex_model,
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


@cli.command()
@click.option("--days", type=int, default=None, help="Override retention_days from config")
@click.pass_context
def cleanup(ctx, days: int | None):
    """Delete old data beyond the retention period."""
    config: Config = ctx.obj["config"]
    retention_days = days if days is not None else config.retention_days

    if retention_days <= 0:
        console.print("[yellow]Retention is disabled (retention_days <= 0)[/yellow]")
        return

    if not config.db_path.exists():
        console.print("[dim]No data yet[/dim]")
        return

    console.print(f"[dim]Cleaning up data older than {retention_days} days...[/dim]")

    from daemon.retention import cleanup_old_data
    from daemon.storage.database import Database

    db = Database(config.db_path)
    result = cleanup_old_data(db, config.data_dir, retention_days)
    db.close()

    freed_mb = result["freed_bytes"] / (1024 * 1024)
    console.print("[green]Cleanup complete:[/green]")
    console.print(f"  Frames deleted:       {result['frames_deleted']}")
    console.print(f"  Summaries deleted:    {result['summaries_deleted']}")
    console.print(f"  Events deleted:       {result['events_deleted']}")
    console.print(f"  Window events deleted:{result['window_events_deleted']}")
    console.print(f"  Files removed:        {result['files_deleted']}")
    console.print(f"  Disk freed:           {freed_mb:.1f} MB")


@cli.command("embed-backfill")
@click.option("--workers", default=5, type=int, help="Parallel workers (default: 5)")
@click.option(
    "--type",
    "item_types",
    multiple=True,
    type=click.Choice(["frame", "chat", "summary"]),
    help="Types to backfill (default: all)",
)
@click.pass_context
def embed_backfill(ctx, workers: int, item_types: tuple[str, ...]):
    """Backfill embeddings for historical frames, chat messages, and summaries."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from threading import Lock

    from rich.progress import Progress

    config: Config = ctx.obj["config"]

    if not config.embedding.enabled:
        console.print("[yellow]Embedding is disabled in config[/yellow]")
        return

    if not config.db_path.exists():
        console.print("[dim]No data yet[/dim]")
        return

    from daemon.embedding import Embedder
    from daemon.storage.database import Database

    db = Database(config.db_path, embedding_dimensions=config.embedding.dimensions)
    embedder = Embedder(model=config.embedding.model, dimensions=config.embedding.dimensions)

    if embedder._get_client() is None:
        console.print("[red]GEMINI_API_KEY not set — cannot embed[/red]")
        db.close()
        return

    types_to_run = set(item_types) if item_types else {"frame", "chat", "summary"}
    stats = {"frame": [0, 0], "chat": [0, 0], "summary": [0, 0]}  # [success, fail]
    db_lock = Lock()

    def embed_one_frame(fid: int) -> bool:
        try:
            with db_lock:
                row = db._conn.execute("SELECT * FROM frames WHERE id = ?", (fid,)).fetchone()
            if not row:
                return False
            frame = db._row_to_frame(row)
            embedding = embedder.embed_frame(frame, config.data_dir)
            if embedding:
                preview = frame.claude_description[:200] if frame.claude_description else frame.activity
                with db_lock:
                    db.insert_embedding("frame", fid, frame.timestamp.isoformat(), preview, embedding)
                return True
            return False
        except Exception as e:
            console.print(f"[red]Frame {fid}: {e}[/red]")
            return False

    def embed_one_chat(mid: int) -> bool:
        try:
            with db_lock:
                row = db._conn.execute("SELECT * FROM chat_messages WHERE id = ?", (mid,)).fetchone()
            if not row:
                return False
            msg = db._row_to_chat_message(row)
            embedding = embedder.embed_chat_message(msg)
            if embedding:
                preview = f"{msg.author_name}: {msg.content[:200]}"
                with db_lock:
                    db.insert_embedding("chat", mid, msg.timestamp.isoformat(), preview, embedding)
                return True
            return False
        except Exception as e:
            console.print(f"[red]Chat {mid}: {e}[/red]")
            return False

    def embed_one_summary(sid: int) -> bool:
        try:
            with db_lock:
                row = db._conn.execute("SELECT * FROM summaries WHERE id = ?", (sid,)).fetchone()
            if not row:
                return False
            summary = db._row_to_summary(row)
            embedding = embedder.embed_summary(summary)
            if embedding:
                preview = f"[{summary.scale}] {summary.content[:200]}"
                with db_lock:
                    db.insert_embedding("summary", sid, summary.timestamp.isoformat(), preview, embedding)
                return True
            return False
        except Exception as e:
            console.print(f"[red]Summary {sid}: {e}[/red]")
            return False

    def run_parallel(task_id, ids: list[int], fn, type_key: str):
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(fn, item_id): item_id for item_id in ids}
            for future in as_completed(futures):
                ok = future.result()
                if ok:
                    stats[type_key][0] += 1
                else:
                    stats[type_key][1] += 1
                progress.advance(task_id)

    console.print(f"[dim]Workers: {workers} parallel threads[/dim]")

    with Progress(console=console) as progress:
        if "frame" in types_to_run:
            all_frame_ids = db.get_unembedded_frame_ids(limit=100000)
            if all_frame_ids:
                task = progress.add_task(f"[cyan]Frames ({len(all_frame_ids)})", total=len(all_frame_ids))
                run_parallel(task, all_frame_ids, embed_one_frame, "frame")
            else:
                console.print("[dim]All frames already embedded[/dim]")

        if "chat" in types_to_run:
            all_chat_ids = db.get_unembedded_chat_ids(limit=100000)
            if all_chat_ids:
                task = progress.add_task(f"[green]Chat ({len(all_chat_ids)})", total=len(all_chat_ids))
                run_parallel(task, all_chat_ids, embed_one_chat, "chat")
            else:
                console.print("[dim]All chat messages already embedded[/dim]")

        if "summary" in types_to_run:
            all_sum_ids = db.get_unembedded_summary_ids(limit=100000)
            if all_sum_ids:
                task = progress.add_task(f"[blue]Summaries ({len(all_sum_ids)})", total=len(all_sum_ids))
                run_parallel(task, all_sum_ids, embed_one_summary, "summary")
            else:
                console.print("[dim]All summaries already embedded[/dim]")

    total_ok = sum(v[0] for v in stats.values())
    total_fail = sum(v[1] for v in stats.values())
    console.print()
    console.print(
        Panel(
            f"Frames:    {stats['frame'][0]} embedded, {stats['frame'][1]} failed\n"
            f"Chat:      {stats['chat'][0]} embedded, {stats['chat'][1]} failed\n"
            f"Summaries: {stats['summary'][0]} embedded, {stats['summary'][1]} failed\n"
            f"Total:     {total_ok} embedded, {total_fail} failed\n"
            f"Vec items: {db.get_embedding_count()} total in store",
            title="Backfill Complete",
            border_style="green" if total_fail == 0 else "yellow",
        )
    )
    db.close()


def _parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError as e:
        raise click.BadParameter(f"Invalid date: {s} (expected YYYY-MM-DD)") from e


# ─── JSON data helpers ───────────────────────────────────────────────────────


def _frame_to_dict(f) -> dict:
    """Convert a Frame dataclass to a JSON-serializable dict."""
    return {
        "id": f.id,
        "timestamp": f.timestamp.isoformat(),
        "path": f.path,
        "screen_path": f.screen_path,
        "audio_path": f.audio_path,
        "transcription": f.transcription,
        "brightness": f.brightness,
        "motion_score": f.motion_score,
        "scene_type": f.scene_type.value,
        "description": f.claude_description,
        "activity": f.activity,
        "foreground_window": f.foreground_window,
        "idle_seconds": f.idle_seconds,
    }


def _summary_to_dict(s) -> dict:
    return {
        "id": s.id,
        "timestamp": s.timestamp.isoformat(),
        "scale": s.scale,
        "content": s.content,
        "frame_count": s.frame_count,
    }


# ─── Phase 1-3: Data read commands ──────────────────────────────────────────


@cli.command("frames-list")
@click.argument("target_date", required=False)
@click.option("--limit", default=100, help="Max frames to return")
@click.option("--json", "as_json", is_flag=True, default=True, help="Output JSON (default)")
@click.pass_context
def frames_list(ctx, target_date: str | None, limit: int, as_json: bool):
    """List frames for a date (JSON output for Claude Code)."""
    import json as json_mod

    config: Config = ctx.obj["config"]
    d = _parse_date(target_date) if target_date else date.today()

    if not config.db_path.exists():
        click.echo(json_mod.dumps({"frames": [], "count": 0}))
        return

    from daemon.storage.database import Database

    db = Database(config.db_path)
    frames = db.get_frames_for_date(d)
    db.close()

    if limit and len(frames) > limit:
        frames = frames[-limit:]

    click.echo(
        json_mod.dumps(
            {
                "date": d.isoformat(),
                "count": len(frames),
                "frames": [_frame_to_dict(f) for f in frames],
            },
            ensure_ascii=False,
        )
    )


@cli.command("frames-get")
@click.argument("frame_id", type=int)
@click.option("--include-image", is_flag=True, help="Include base64 encoded image")
@click.pass_context
def frames_get(ctx, frame_id: int, include_image: bool):
    """Get a single frame by ID (JSON output)."""
    import json as json_mod

    config: Config = ctx.obj["config"]
    if not config.db_path.exists():
        click.echo(json_mod.dumps({"error": "no database"}))
        return

    from daemon.storage.database import Database

    db = Database(config.db_path)
    frame = db.get_frame_by_id(frame_id)
    db.close()

    if not frame:
        click.echo(json_mod.dumps({"error": f"frame {frame_id} not found"}))
        return

    result = _frame_to_dict(frame)
    result["data_dir"] = str(config.data_dir.resolve())

    if include_image:
        import base64

        for key in ("path", "screen_path"):
            fpath = config.data_dir / result[key] if result[key] else None
            if fpath and fpath.exists():
                result[f"{key}_base64"] = base64.b64encode(fpath.read_bytes()).decode()

    click.echo(json_mod.dumps(result, ensure_ascii=False))


@cli.command("frames-pending")
@click.option("--limit", default=50, help="Max pending frames to return")
@click.pass_context
def frames_pending(ctx, limit: int):
    """List frames pending analysis (JSON output)."""
    import json as json_mod

    config: Config = ctx.obj["config"]
    if not config.db_path.exists():
        click.echo(json_mod.dumps({"frames": [], "count": 0}))
        return

    from daemon.storage.database import Database

    db = Database(config.db_path)
    frames = db.get_pending_frames(limit=limit)
    db.close()

    click.echo(
        json_mod.dumps(
            {
                "count": len(frames),
                "data_dir": str(config.data_dir.resolve()),
                "frames": [_frame_to_dict(f) for f in frames],
            },
            ensure_ascii=False,
        )
    )


@cli.command("summary-list")
@click.argument("target_date", required=False)
@click.option("--scale", type=click.Choice(["10m", "30m", "1h", "6h", "12h", "24h"]), default=None)
@click.pass_context
def summary_list(ctx, target_date: str | None, scale: str | None):
    """List summaries for a date (JSON output)."""
    import json as json_mod

    config: Config = ctx.obj["config"]
    d = _parse_date(target_date) if target_date else date.today()

    if not config.db_path.exists():
        click.echo(json_mod.dumps({"summaries": [], "count": 0}))
        return

    from daemon.storage.database import Database

    db = Database(config.db_path)
    sums = db.get_summaries_for_date(d, scale)
    db.close()

    click.echo(
        json_mod.dumps(
            {
                "date": d.isoformat(),
                "scale_filter": scale,
                "count": len(sums),
                "summaries": [_summary_to_dict(s) for s in sums],
            },
            ensure_ascii=False,
        )
    )


@cli.command("activity-stats")
@click.option("--days", default=7, help="Number of days to include")
@click.pass_context
def activity_stats_cmd(ctx, days: int):
    """Show activity statistics for a date range (JSON output)."""
    import json as json_mod

    config: Config = ctx.obj["config"]
    if not config.db_path.exists():
        click.echo(json_mod.dumps({"stats": [], "days": days}))
        return

    from daemon.storage.database import Database

    db = Database(config.db_path)
    stats = db.get_activity_stats_range(days=days)
    mappings = db.get_all_activity_mappings()
    db.close()

    click.echo(
        json_mod.dumps(
            {
                "days": days,
                "stats": stats,
                "mappings": mappings,
            },
            ensure_ascii=False,
        )
    )


@cli.command("search")
@click.argument("query")
@click.option("--limit", default=20)
@click.option("--type", "search_type", type=click.Choice(["frames", "summaries", "all"]), default="all")
@click.pass_context
def search_cmd(ctx, query: str, limit: int, search_type: str):
    """Full-text search across frames and summaries (JSON output)."""
    import json as json_mod

    config: Config = ctx.obj["config"]
    if not config.db_path.exists():
        click.echo(json_mod.dumps({"results": []}))
        return

    from daemon.storage.database import Database

    db = Database(config.db_path)
    results: dict = {"query": query}

    if search_type in ("frames", "all"):
        frames = db.search_frames(query, limit=limit)
        results["frames"] = [_frame_to_dict(f) for f in frames]

    if search_type in ("summaries", "all"):
        sums = db.search_summaries(query, limit=limit)
        results["summaries"] = [_summary_to_dict(s) for s in sums]

    db.close()
    click.echo(json_mod.dumps(results, ensure_ascii=False))


@cli.command("status-json")
@click.pass_context
def status_json(ctx):
    """Show daemon status as JSON (for Claude Code)."""
    import json as json_mod

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

    result: dict = {
        "running": running,
        "pid": pid,
        "data_dir": str(config.data_dir.resolve()),
        "db_path": str(config.db_path.resolve()),
        "llm_provider": config.llm.provider,
        "ws_port": 3004,
    }

    if config.db_path.exists():
        from daemon.storage.database import Database

        db = Database(config.db_path)
        result["frames_today"] = db.get_frame_count_for_date(date.today())
        latest = db.get_latest_frame()
        if latest:
            result["latest_frame"] = _frame_to_dict(latest)
        sums = db.get_summaries_for_date(date.today())
        result["summaries_today"] = len(sums)
        result["memo_today"] = db.get_memo(date.today())
        db.close()

    click.echo(json_mod.dumps(result, ensure_ascii=False))


# ─── Phase 1-4: Data write commands ─────────────────────────────────────────


@cli.command("frames-update")
@click.argument("frame_id", type=int)
@click.option("--analysis", "description", default=None, help="Analysis description")
@click.option("--activity", default=None, help="Activity category")
@click.option("--meta-category", default="other", help="Meta category")
@click.pass_context
def frames_update(ctx, frame_id: int, description: str | None, activity: str | None, meta_category: str):
    """Update frame analysis (used by Claude Code to send results)."""
    import json as json_mod

    config: Config = ctx.obj["config"]
    if not config.db_path.exists():
        click.echo(json_mod.dumps({"error": "no database"}))
        return

    from daemon.activity import ActivityManager
    from daemon.storage.database import Database

    db = Database(config.db_path)
    frame = db.get_frame_by_id(frame_id)
    if not frame:
        click.echo(json_mod.dumps({"error": f"frame {frame_id} not found"}))
        db.close()
        return

    desc = description or frame.claude_description
    act = activity or frame.activity

    if activity:
        activity_mgr = ActivityManager(db)
        act, _ = activity_mgr.normalize_and_register(act, meta_category)

    db.update_frame_analysis(frame_id, desc, act)
    db.close()

    click.echo(
        json_mod.dumps(
            {
                "ok": True,
                "frame_id": frame_id,
                "description": desc[:200],
                "activity": act,
            },
            ensure_ascii=False,
        )
    )


@cli.command("summary-create")
@click.option("--scale", required=True, type=click.Choice(["10m", "30m", "1h", "6h", "12h", "24h"]))
@click.option("--content", required=True, help="Summary content")
@click.option("--frame-count", default=0, help="Number of frames covered")
@click.pass_context
def summary_create(ctx, scale: str, content: str, frame_count: int):
    """Create a new summary (used by Claude Code)."""
    import json as json_mod

    config: Config = ctx.obj["config"]
    if not config.db_path.exists():
        click.echo(json_mod.dumps({"error": "no database"}))
        return

    from daemon.storage.database import Database
    from daemon.storage.models import Summary

    db = Database(config.db_path)
    summary = Summary(
        timestamp=datetime.now(),
        scale=scale,
        content=content,
        frame_count=frame_count,
    )
    summary.id = db.insert_summary(summary)
    db.close()

    click.echo(
        json_mod.dumps(
            {
                "ok": True,
                "summary_id": summary.id,
                "scale": scale,
                "content": content[:200],
            },
            ensure_ascii=False,
        )
    )


@cli.command("memo-set")
@click.option("--date", "target_date", default=None, help="Date (YYYY-MM-DD, default: today)")
@click.option("--content", required=True, help="Memo content")
@click.pass_context
def memo_set(ctx, target_date: str | None, content: str):
    """Set daily memo (used by Claude Code)."""
    import json as json_mod

    config: Config = ctx.obj["config"]
    d = _parse_date(target_date) if target_date else date.today()

    if not config.db_path.exists():
        click.echo(json_mod.dumps({"error": "no database"}))
        return

    from daemon.storage.database import Database

    db = Database(config.db_path)
    db.upsert_memo(d, content)
    db.close()

    click.echo(
        json_mod.dumps(
            {
                "ok": True,
                "date": d.isoformat(),
                "content": content[:200],
            },
            ensure_ascii=False,
        )
    )


# ─── Phase 2-2: connect --stream ─────────────────────────────────────────────


@cli.command("connect")
@click.option("--port", default=3004, help="WebSocket server port")
@click.option("--stream", is_flag=True, help="Stream events to stdout as ndjson")
@click.pass_context
def connect(ctx, port: int, stream: bool):
    """Connect to daemon WebSocket. With --stream, output events as ndjson."""
    import asyncio
    import json as json_mod
    import sys

    async def _connect():
        try:
            import websockets
        except ImportError:
            click.echo(json_mod.dumps({"error": "websockets not installed. pip install websockets"}))
            return

        uri = f"ws://127.0.0.1:{port}"
        try:
            async with websockets.connect(uri) as ws:
                # Read welcome message
                welcome = await ws.recv()
                if not stream:
                    # Just verify connectivity and exit
                    click.echo(welcome)
                    return

                # Stream mode: output all events as ndjson
                sys.stdout.write(welcome + "\n")
                sys.stdout.flush()
                async for msg in ws:
                    sys.stdout.write(msg + "\n")
                    sys.stdout.flush()
        except ConnectionRefusedError:
            click.echo(
                json_mod.dumps(
                    {
                        "error": f"Cannot connect to daemon WebSocket at {uri}. Is the daemon running?",
                    }
                )
            )
        except KeyboardInterrupt:
            pass

    asyncio.run(_connect())


# ─── Phase 2-3: watch ────────────────────────────────────────────────────────


@cli.command("watch")
@click.option("--port", default=3004, help="WebSocket server port")
@click.option("--type", "event_type", default="analyze_request", help="Event type to wait for")
@click.option("--timeout", default=120, help="Timeout in seconds (0 = infinite)")
@click.pass_context
def watch(ctx, port: int, event_type: str, timeout: int):
    """Wait for the next event of a given type and output it (single-shot).

    Perfect for Claude Code loop:
        while true; do vida watch --type analyze_request; done
    """
    import asyncio
    import contextlib
    import json as json_mod
    import sys

    async def _wait_for_event():
        try:
            import websockets
        except ImportError:
            click.echo(json_mod.dumps({"error": "websockets not installed"}))
            return

        uri = f"ws://127.0.0.1:{port}"
        try:
            async with websockets.connect(uri) as ws:
                cm = asyncio.timeout(timeout) if timeout > 0 else contextlib.nullcontext()
                try:
                    async with cm:
                        async for msg in ws:
                            try:
                                data = json_mod.loads(msg)
                            except json_mod.JSONDecodeError:
                                continue

                            if data.get("type") == event_type:
                                sys.stdout.write(msg + "\n")
                                sys.stdout.flush()
                                return
                except TimeoutError:
                    click.echo(json_mod.dumps({"error": "timeout", "waited_seconds": timeout}))
        except ConnectionRefusedError:
            click.echo(
                json_mod.dumps(
                    {
                        "error": f"Cannot connect to daemon WebSocket at {uri}. Is the daemon running?",
                    }
                )
            )

    asyncio.run(_wait_for_event())
