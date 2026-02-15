"""Constants and configuration for STJ search tool."""

from pathlib import Path

CKAN_BASE_URL = "https://dadosabertos.web.stj.jus.br/api/3/action"

DATASETS = [
    "espelhos-de-acordaos-corte-especial",
    "espelhos-de-acordaos-primeira-secao",
    "espelhos-de-acordaos-primeira-turma",
    "espelhos-de-acordaos-quarta-turma",
    "espelhos-de-acordaos-quinta-turma",
    "espelhos-de-acordaos-segunda-secao",
    "espelhos-de-acordaos-segunda-turma",
    "espelhos-de-acordaos-sexta-turma",
    "espelhos-de-acordaos-terceira-secao",
    "espelhos-de-acordaos-terceira-turma",
]

DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "stj.db"
