"""Sync orchestrator: download datasets and upsert into DB."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from . import client, db
from .config import DATASETS
from .models import Acordao

console = Console()


def sync_dataset(
    conn: sqlite3.Connection,
    dataset: str,
    *,
    force: bool = False,
    progress: Progress | None = None,
) -> int:
    console.print(f"[bold blue]Dataset:[/] {dataset}")
    resources = client.get_dataset_resources(dataset)
    data_resources = client.filter_data_resources(resources)

    if not data_resources:
        console.print("  [yellow]No data resources found.[/]")
        return 0

    total_upserted = 0
    task_id = None
    if progress:
        task_id = progress.add_task(dataset, total=len(data_resources))

    for res in data_resources:
        res_id = res["id"]
        res_name = res.get("name", "")
        res_format = res.get("format", "").upper()
        res_url = res["url"]

        if not force and db.is_synced(conn, dataset, res_id):
            if progress and task_id is not None:
                progress.advance(task_id)
            continue

        console.print(f"  [dim]Downloading {res_name}...[/]")

        try:
            if res_format == "ZIP":
                json_files = client.download_and_extract_zip(res_url, dataset)
                for json_file in json_files:
                    raw = client.parse_json_file(json_file)
                    records = [Acordao.from_json(r) for r in raw]
                    count = db.upsert_acordaos(conn, records)
                    total_upserted += count
                    json_file.unlink(missing_ok=True)
            else:
                raw = client.download_json(res_url)
                records = [Acordao.from_json(r) for r in raw]
                count = db.upsert_acordaos(conn, records)
                total_upserted += count

            db.mark_synced(conn, dataset, res_id, res_name)
        except Exception as e:
            console.print(f"  [red]Error processing {res_name}: {e}[/]")

        if progress and task_id is not None:
            progress.advance(task_id)

    console.print(f"  [green]{total_upserted} records upserted.[/]")
    return total_upserted


def sync_all(
    conn: sqlite3.Connection,
    *,
    dataset_filter: str | None = None,
    force: bool = False,
) -> int:
    db.init_db(conn)
    datasets = [dataset_filter] if dataset_filter else DATASETS
    total = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        for ds in datasets:
            count = sync_dataset(conn, ds, force=force, progress=progress)
            total += count

    console.print(f"\n[bold green]Sync complete. {total} total records upserted.[/]")
    return total
