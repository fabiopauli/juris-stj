"""CLI interface for STJ jurisprudence search tool."""

from __future__ import annotations

import re

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import db
from .config import DB_PATH, DATASETS
from .sync import sync_all

console = Console()


@click.group()
def cli() -> None:
    """STJ Jurisprudence Search Tool."""


@cli.command()
@click.option("-d", "--dataset", default=None, help="Sync a specific dataset only.")
@click.option("--force", is_flag=True, help="Re-download everything.")
def sync(dataset: str | None, force: bool) -> None:
    """Download and index STJ datasets."""
    if dataset and dataset not in DATASETS:
        console.print(f"[red]Unknown dataset: {dataset}[/]")
        console.print("Available datasets:")
        for ds in DATASETS:
            console.print(f"  {ds}")
        raise SystemExit(1)

    conn = db.get_connection()
    try:
        if force:
            db.clear_sync_state(conn, dataset)
        sync_all(conn, dataset_filter=dataset, force=force)
    finally:
        conn.close()


@cli.command()
@click.argument("query")
@click.option("-m", "--ministro", default=None, help="Filter by ministro relator.")
@click.option("-c", "--classe", default=None, help="Filter by sigla classe (e.g. REsp).")
@click.option("--desde", default=None, help="Filter decisions from date (YYYYMMDD).")
@click.option("-n", "--limit", default=20, help="Max results (default: 20).")
@click.option("--data", "order", flag_value="data", default=True, help="Sort by date, newest first (default).")
@click.option("--palavra", "order", flag_value="palavra", help="Sort by relevance (BM25).")
@click.option("--stats", is_flag=True, help="Show statistics instead of individual results.")
def busca(query: str, ministro: str | None, classe: str | None, desde: str | None, limit: int, order: str, stats: bool) -> None:
    """Full-text search on STJ acordaos.

    Supports FTS5 syntax: AND, OR, "exact phrases", prefix*.
    """
    conn = db.get_connection()
    try:
        db.init_db(conn)
        if stats:
            _busca_stats(conn, query, ministro=ministro, classe=classe, desde=desde)
        else:
            _busca_results(conn, query, ministro=ministro, classe=classe, desde=desde, limit=limit, order=order)
    except Exception as e:
        console.print(f"[red]Search error: {e}[/]")
        raise SystemExit(1)
    finally:
        conn.close()


def _busca_results(
    conn, query: str, *, ministro: str | None, classe: str | None, desde: str | None, limit: int, order: str
) -> None:
    results = db.search(conn, query, ministro=ministro, classe=classe, desde=desde, limit=limit, order=order)
    if not results:
        console.print("[yellow]No results found.[/]")
        return

    table = Table(title=f"Results for: {query}", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("ID", style="cyan", width=10)
    table.add_column("Classe", width=10)
    table.add_column("Relator", width=20)
    table.add_column("Data", width=10)
    table.add_column("Ementa")

    for i, row in enumerate(results, 1):
        ementa = row["ementa"] or ""
        table.add_row(
            str(i),
            row["id"],
            row["sigla_classe"],
            row["ministro_relator"],
            row["data_decisao"],
            ementa,
        )

    console.print(table)
    console.print(f"\n[dim]{len(results)} results shown.[/]")


def _busca_stats(
    conn, query: str, *, ministro: str | None, classe: str | None, desde: str | None
) -> None:
    s = db.search_stats(conn, query, ministro=ministro, classe=classe, desde=desde)
    if s["total"] == 0:
        console.print("[yellow]No results found.[/]")
        return

    filters = []
    if ministro:
        filters.append(f"ministro={ministro}")
    if classe:
        filters.append(f"classe={classe}")
    if desde:
        filters.append(f"desde={desde}")
    subtitle = f"  filters: {', '.join(filters)}" if filters else ""
    console.print(Panel(
        f"[bold]{s['total']:,}[/] matching records",
        title=f"Stats: {query}",
        subtitle=subtitle,
        border_style="blue",
    ))

    if s["by_orgao"]:
        table = Table(title="By Orgao Julgador")
        table.add_column("Orgao Julgador", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("%", justify="right", style="dim")
        for row in s["by_orgao"]:
            pct = row["cnt"] / s["total"] * 100
            table.add_row(row["orgao_julgador"], f"{row['cnt']:,}", f"{pct:.1f}")
        console.print(table)

    if s["by_classe"]:
        table = Table(title="Top 10 Classes")
        table.add_column("Classe", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("%", justify="right", style="dim")
        for row in s["by_classe"]:
            pct = row["cnt"] / s["total"] * 100
            table.add_row(row["sigla_classe"], f"{row['cnt']:,}", f"{pct:.1f}")
        console.print(table)

    if s["by_relator"]:
        table = Table(title="Top 10 Relatores")
        table.add_column("Ministro Relator", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("%", justify="right", style="dim")
        for row in s["by_relator"]:
            pct = row["cnt"] / s["total"] * 100
            table.add_row(row["ministro_relator"], f"{row['cnt']:,}", f"{pct:.1f}")
        console.print(table)

    if s["by_year"]:
        table = Table(title="By Year (last 15)")
        table.add_column("Year", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("%", justify="right", style="dim")
        for row in s["by_year"]:
            pct = row["cnt"] / s["total"] * 100
            table.add_row(row["ano"], f"{row['cnt']:,}", f"{pct:.1f}")
        console.print(table)


def _format_citation(row) -> str:
    """Build a legal citation string from a DB row."""
    parts = ["STJ."]

    sigla = row["sigla_classe"] or ""
    num_raw = row["numero_processo"] or ""
    if sigla and num_raw:
        try:
            num_fmt = f"{int(num_raw):,}".replace(",", ".")
        except ValueError:
            num_fmt = num_raw
        parts.append(f"{sigla} n. {num_fmt}")

    relator = row["ministro_relator"] or ""
    if relator:
        parts.append(f"relator Ministro {relator.title()}")

    orgao = row["orgao_julgador"] or ""
    if orgao:
        parts.append(orgao.title())

    data_dec = row["data_decisao"] or ""
    if len(data_dec) == 8:
        parts.append(f"julgado em {int(data_dec[6:])}/{int(data_dec[4:6])}/{data_dec[:4]}")

    data_pub = row["data_publicacao"] or ""
    if data_pub:
        m = re.match(r"^(\S+)\s+DATA:\s*(\d{2}/\d{2}/\d{4})", data_pub)
        if m:
            source = m.group(1)
            d, mo, y = m.group(2).split("/")
            parts.append(f"{source} de {int(d)}/{int(mo)}/{y}")

    return "(" + ", ".join(parts) + ")."


@cli.command()
@click.argument("record_id")
def ver(record_id: str) -> None:
    """View full details of an acordao by ID."""
    conn = db.get_connection()
    try:
        db.init_db(conn)
        row = db.get_by_id(conn, record_id)
    finally:
        conn.close()

    if not row:
        console.print(f"[red]Record not found: {record_id}[/]")
        raise SystemExit(1)

    if row["ementa"]:
        console.print(Panel(row["ementa"], title="Ementa", border_style="green"))

    citation = _format_citation(row)
    console.print(Panel(citation, title="Citação", border_style="dim"))

    if row["decisao"]:
        console.print(Panel(row["decisao"], title="Decisao", border_style="yellow"))

    if row["informacoes_complementares"]:
        console.print(Panel(row["informacoes_complementares"], title="Informacoes Complementares", border_style="cyan"))

    if row["tese_juridica"]:
        console.print(Panel(row["tese_juridica"], title="Tese Juridica", border_style="magenta"))

    if row["jurisprudencia_citada"]:
        console.print(Panel(row["jurisprudencia_citada"], title="Jurisprudencia Citada", border_style="dim"))

    if row["notas"]:
        console.print(Panel(row["notas"], title="Notas", border_style="dim"))

    if row["termos_auxiliares"]:
        console.print(Panel(row["termos_auxiliares"], title="Termos Auxiliares", border_style="dim"))

    if row["referencias_legislativas"]:
        console.print(Panel(row["referencias_legislativas"], title="Referencias Legislativas", border_style="dim"))

    if row["tema"]:
        console.print(f"[bold]Tema:[/] {row['tema']}")

    title = f"{row['sigla_classe']} - Processo {row['numero_processo']}"
    content = Text()

    fields = [
        ("ID", "id"),
        ("Documento", "numero_documento"),
        ("Processo", "numero_processo"),
        ("Registro", "numero_registro"),
        ("Classe", "descricao_classe"),
        ("Classe Padronizada", "classe_padronizada"),
        ("Orgao Julgador", "orgao_julgador"),
        ("Relator", "ministro_relator"),
        ("Tipo Decisao", "tipo_decisao"),
        ("Data Decisao", "data_decisao"),
        ("Data Publicacao", "data_publicacao"),
    ]

    for label, key in fields:
        content.append(f"{label}: ", style="bold")
        content.append(f"{row[key] or ''}\n")

    content.append("\n")
    console.print(Panel(content, title=title, border_style="blue"))


@cli.command()
def info() -> None:
    """Show database statistics and sync status."""
    conn = db.get_connection()
    try:
        db.init_db(conn)
        stats = db.get_stats(conn)
    finally:
        conn.close()

    console.print(Panel(f"[bold]{stats['total']:,}[/] total records", title="Database", border_style="blue"))

    if stats["by_orgao"]:
        table = Table(title="Records by Orgao Julgador")
        table.add_column("Orgao Julgador", style="cyan")
        table.add_column("Count", justify="right")
        for row in stats["by_orgao"]:
            table.add_row(row["orgao_julgador"], f"{row['cnt']:,}")
        console.print(table)

    if stats["by_classe"]:
        table = Table(title="Top 20 Classes")
        table.add_column("Classe", style="cyan")
        table.add_column("Count", justify="right")
        for row in stats["by_classe"]:
            table.add_row(row["sigla_classe"], f"{row['cnt']:,}")
        console.print(table)

    if stats["sync_info"]:
        table = Table(title="Sync Status")
        table.add_column("Dataset", style="cyan")
        table.add_column("Resources", justify="right")
        table.add_column("Last Sync")
        for row in stats["sync_info"]:
            table.add_row(row["dataset"], str(row["resources"]), row["last_sync"])
        console.print(table)
    else:
        console.print("[yellow]No datasets synced yet. Run 'stj sync' to get started.[/]")
