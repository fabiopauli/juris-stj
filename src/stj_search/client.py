"""CKAN API client for downloading STJ datasets."""

from __future__ import annotations

import json
import time
import zipfile
from pathlib import Path

import httpx

from .config import CKAN_BASE_URL, DATA_DIR

TIMEOUT = httpx.Timeout(30.0, read=120.0)
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


def _request_with_retry(method: str, url: str, **kwargs) -> httpx.Response:
    for attempt in range(MAX_RETRIES):
        try:
            with httpx.Client(timeout=TIMEOUT) as client:
                resp = getattr(client, method)(url, **kwargs)
                resp.raise_for_status()
                return resp
        except (httpx.HTTPStatusError, httpx.TransportError) as e:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_DELAY * (attempt + 1)
                time.sleep(wait)
            else:
                raise


def get_dataset_resources(dataset: str) -> list[dict]:
    url = f"{CKAN_BASE_URL}/package_show"
    resp = _request_with_retry("get", url, params={"id": dataset})
    result = resp.json()["result"]
    return result["resources"]


def filter_data_resources(resources: list[dict]) -> list[dict]:
    return [
        r
        for r in resources
        if r.get("format", "").upper() in ("JSON", "ZIP")
        and not r.get("name", "").startswith("dicionario")
    ]


def download_json(url: str) -> list[dict]:
    resp = _request_with_retry("get", url, follow_redirects=True)
    return resp.json()


def download_and_extract_zip(url: str, dataset: str) -> list[Path]:
    dest_dir = DATA_DIR / dataset
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / "archive.zip"

    for attempt in range(MAX_RETRIES):
        try:
            with httpx.Client(timeout=TIMEOUT) as client:
                with client.stream("GET", url, follow_redirects=True) as resp:
                    resp.raise_for_status()
                    with open(zip_path, "wb") as f:
                        for chunk in resp.iter_bytes(chunk_size=8192):
                            f.write(chunk)
            break
        except (httpx.HTTPStatusError, httpx.TransportError):
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                raise

    extracted = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if name.endswith(".json"):
                zf.extract(name, dest_dir)
                extracted.append(dest_dir / name)
    zip_path.unlink()
    return extracted


def parse_json_file(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
