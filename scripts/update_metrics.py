#!/usr/bin/env python3
"""Build local README cards from public GitHub REST API data (stdlib only).

Run: python3 scripts/update_metrics.py --username AdevTC
Offline: add --snapshot /path/to/metrics-snapshot.json

Snapshot schema: {retrieved_at_utc, profile, repos, languages}; profile and
repos are complete public API responses; languages maps owner/repo to its
GET /repos/{owner}/{repo}/languages response. No token is ever persisted.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


API_ROOT = "https://api.github.com"
API_VERSION = "2026-03-10"
ROOT = Path(__file__).resolve().parents[1]
USERNAME_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
REPO_PATTERN = re.compile(r"[A-Za-z0-9_.-]+\Z")
MONTHS_ES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


class MetricsError(Exception):
    """Expected failure: do not replace the last successfully generated cards."""


def madrid_datetime(value):
    try:
        return datetime.fromisoformat(value).astimezone(ZoneInfo("Europe/Madrid"))
    except ZoneInfoNotFoundError:
        raise MetricsError(
            "Falta la base de zonas horarias. Usa el workflow de GitHub "
            "o instala tzdata en tu entorno Python. Se conservan las tarjetas anteriores."
        ) from None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Keep credentials on the one API origin explicitly requested.
        return None


def api_get(path, token=""):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "AdevTC-profile-metrics",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(API_ROOT + path, headers=headers)
    try:
        with build_opener(NoRedirect).open(request, timeout=20) as response:
            if response.status != 200:
                raise MetricsError("La API no devolvió una respuesta completa.")
            return json.load(response)
    except HTTPError as exc:
        # Never print a response body, request headers, or token.
        raise MetricsError(f"GitHub respondió HTTP {exc.code}. Se conservan las tarjetas anteriores.") from None
    except (URLError, TimeoutError, OSError, json.JSONDecodeError):
        raise MetricsError("No se pudo leer la API de GitHub. Se conservan las tarjetas anteriores.") from None


def check_repositories(profile, repos, username):
    if not isinstance(profile, dict) or str(profile.get("login", "")).lower() != username.lower():
        raise MetricsError("El perfil no corresponde al usuario solicitado.")
    count = profile.get("public_repos")
    if type(count) is not int or count < 0 or not isinstance(repos, list):
        raise MetricsError("Faltan datos del perfil o del listado de repositorios.")
    if len(repos) != count:
        raise MetricsError("El listado de repositorios está incompleto o ha cambiado durante la consulta.")
    seen = set()
    selected = []
    forks = 0
    for repo in repos:
        if not isinstance(repo, dict):
            raise MetricsError("El listado de repositorios contiene una respuesta no válida.")
        name = repo.get("name")
        owner = repo.get("owner", {}).get("login", "")
        if not isinstance(name, str) or not REPO_PATTERN.fullmatch(name):
            raise MetricsError("Falta un nombre de repositorio válido.")
        if not isinstance(owner, str) or owner.lower() != username.lower():
            raise MetricsError("El listado contiene repositorios de otro propietario.")
        if repo.get("private") is not False or type(repo.get("fork")) is not bool:
            raise MetricsError("No se ha podido confirmar la visibilidad pública del repositorio.")
        full_name = repo.get("full_name")
        if full_name != f"{owner}/{name}" or full_name.lower() in seen:
            raise MetricsError("El listado contiene un repositorio duplicado o no válido.")
        seen.add(full_name.lower())
        if repo["fork"]:
            forks += 1
        elif name.lower() != username.lower():
            selected.append(repo)
    return selected, forks


def fetch_snapshot(username):
    token = os.environ.get("GITHUB_TOKEN", "")
    user_path = "/users/" + quote(username, safe="")
    profile = api_get(user_path, token)
    repos = []
    for page in range(1, 101):
        batch = api_get(user_path + f"/repos?type=owner&sort=full_name&direction=asc&per_page=100&page={page}", token)
        if not isinstance(batch, list):
            raise MetricsError("GitHub no devolvió un listado válido de repositorios.")
        repos.extend(batch)
        if len(batch) < 100:
            break
    else:
        raise MetricsError("El listado excede el límite previsto; no se publican datos parciales.")
    selected, _ = check_repositories(profile, repos, username)
    languages = {}
    for repo in selected:
        owner, name = repo["full_name"].split("/", 1)
        path = "/repos/" + quote(owner, safe="") + "/" + quote(name, safe="") + "/languages"
        languages[repo["full_name"]] = api_get(path, token)
    return {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "profile": profile,
        "repos": repos,
        "languages": languages,
    }


def aggregate(snapshot, username):
    if not isinstance(snapshot, dict):
        raise MetricsError("El snapshot no es válido.")
    selected, forks = check_repositories(snapshot.get("profile"), snapshot.get("repos"), username)
    try:
        observed = datetime.fromisoformat(snapshot["retrieved_at_utc"].replace("Z", "+00:00"))
        if observed.tzinfo is None:
            raise ValueError
    except (KeyError, TypeError, AttributeError, ValueError):
        raise MetricsError("Falta una fecha de consulta válida con zona horaria.") from None
    raw_languages = snapshot.get("languages")
    if not isinstance(raw_languages, dict):
        raise MetricsError("Faltan los datos de lenguajes.")
    totals = Counter()
    repos_with_code = 0
    for repo in selected:
        langs = raw_languages.get(repo["full_name"])
        if not isinstance(langs, dict):
            raise MetricsError("Falta la respuesta de lenguajes de un repositorio; no se publican datos parciales.")
        for language, size in langs.items():
            if not isinstance(language, str) or not language.strip() or len(language) > 80:
                raise MetricsError("GitHub devolvió un nombre de lenguaje no válido.")
            if type(size) is not int or size < 0:
                raise MetricsError("GitHub devolvió un tamaño de lenguaje no válido.")
            if size:
                totals[language] += size
        repos_with_code += int(any(langs.values()))
    total_bytes = sum(totals.values())
    languages = [
        {"name": name, "bytes": size, "percent": round(size / total_bytes * 100, 6)}
        for name, size in sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    ]
    return {
        "schema_version": 1,
        "username": snapshot["profile"]["login"],
        "updated_at_utc": observed.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "public_repositories": snapshot["profile"]["public_repos"],
        "repository_count_scope": "Todos los repositorios públicos propios; incluye el repositorio de perfil y los forks públicos.",
        "language_scope": {
            "description": "Bytes de código en repositorios públicos propios, sin forks ni repositorio de perfil. Incluye repositorios archivados.",
            "repositories_queried": len(selected),
            "repositories_with_detected_code": repos_with_code,
            "excluded_forks": forks,
            "excluded_profile_name": username,
        },
        "total_public_code_bytes": total_bytes,
        "languages": languages,
        "sources": [
            API_ROOT + "/users/" + username,
            API_ROOT + "/users/" + username + "/repos?type=owner&per_page=100",
            "https://docs.github.com/en/rest/repos/repos#list-repository-languages",
        ],
    }


def render_svg(metrics, dark):
    bg, surface, text, muted, border, accent = (
        ("#0B1220", "#101D2E", "#F4F8FB", "#9AAEC1", "#24374A", "#07E3E3")
        if dark else ("#F4F8FB", "#FFFFFF", "#0B1220", "#536A7E", "#D8E5ED", "#007F86")
    )
    colors = [accent, "#648DFF", "#C49BFF", "#E5AF5F", "#7AB8A8", "#8494A4"]
    all_langs = metrics["languages"]
    shown = [dict(entry) for entry in all_langs[:5]]
    if len(all_langs) > 5:
        rest = sum(entry["bytes"] for entry in all_langs[5:])
        shown.append({"name": "Otros", "bytes": rest, "percent": rest / metrics["total_public_code_bytes"] * 100})
    observed = madrid_datetime(metrics["updated_at_utc"])
    date_es = f"{observed.day:02d} {MONTHS_ES[observed.month - 1]} {observed.year}"
    desc = "; ".join(f"{entry['name']}: {entry['percent']:.2f}%" for entry in shown)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="330" viewBox="0 0 900 330" role="img" aria-labelledby="title desc">',
        '<title id="title">Código público de ' + escape(metrics["username"]) + '</title>',
        '<desc id="desc">' + escape(f"{metrics['public_repositories']} repositorios públicos. Distribución de bytes de código, excluidos forks y perfil: {desc}. Actualizado el {date_es}. No mide experiencia profesional ni dominio de lenguajes.") + '</desc>',
        f'<rect x="1" y="1" width="898" height="328" rx="20" fill="{bg}" stroke="{border}"/>',
        '<g font-family="Arial, Helvetica, sans-serif">',
        f'<text x="32" y="34" fill="{accent}" font-size="11" font-weight="700" letter-spacing="2.2">GITHUB · CÓDIGO PÚBLICO</text>',
        f'<text x="32" y="72" fill="{text}" font-size="28" font-weight="700">Proyectos que puedes explorar.</text>',
        f'<path d="M249 103V255" stroke="{border}"/>',
        f'<text x="32" y="183" fill="{accent}" font-size="76" font-weight="700">{metrics["public_repositories"]}</text>',
        f'<text x="36" y="212" fill="{text}" font-size="16" font-weight="700">Repositorios públicos</text>',
        f'<text x="36" y="237" fill="{muted}" font-size="12">Incluye este perfil</text>',
        f'<text x="282" y="113" fill="{text}" font-size="16" font-weight="700">Lenguajes del código público</text>',
        f'<text x="282" y="134" fill="{muted}" font-size="12">Distribución por bytes · {len(all_langs)} lenguajes detectados</text>',
        '<defs><clipPath id="bar"><rect x="282" y="151" width="580" height="12" rx="6"/></clipPath></defs>',
        f'<rect x="282" y="151" width="580" height="12" rx="6" fill="{surface}"/>',
        '<g clip-path="url(#bar)">',
    ]
    pos = 282.0
    total = metrics["total_public_code_bytes"]
    for i, entry in enumerate(shown):
        width = entry["bytes"] / total * 580 if total else 0
        parts.append(f'<rect x="{pos:.4f}" y="151" width="{width:.4f}" height="12" fill="{colors[i]}"/>')
        pos += width
    parts.append('</g>')
    for i, entry in enumerate(shown):
        x = 282 + (i % 2) * 302
        y = 193 + (i // 2) * 30
        percent = "<0,1 %" if 0 < entry["percent"] < 0.1 else f"{entry['percent']:.1f} %".replace(".", ",")
        name = entry["name"] if len(entry["name"]) < 23 else entry["name"][:21] + "…"
        parts.extend([
            f'<circle cx="{x + 5}" cy="{y - 4}" r="4" fill="{colors[i]}"/>',
            f'<text x="{x + 18}" y="{y}" fill="{text}" font-size="13">{escape(name)}</text>',
            f'<text x="{x + 268}" y="{y}" fill="{muted}" font-size="13" text-anchor="end">{escape(percent)}</text>',
        ])
    if not shown:
        parts.append(f'<text x="282" y="201" fill="{muted}" font-size="14">GitHub no detecta código en los repositorios incluidos.</text>')
    parts.extend([
        f'<path d="M32 279H868" stroke="{border}"/>',
        f'<text x="32" y="304" fill="{muted}" font-size="11">Sin forks ni perfil en los lenguajes. No mide nivel de dominio.</text>',
        f'<text x="868" y="304" fill="{muted}" font-size="11" text-anchor="end">Actualizado: {date_es}</text>',
        '</g></svg>',
    ])
    svg = "\n".join(parts) + "\n"
    try:
        ET.fromstring(svg)
    except ET.ParseError:
        raise MetricsError("No se pudo validar la tarjeta SVG. Se conserva el resultado anterior.") from None
    return svg


def render_mobile_svg(metrics, dark):
    """Readable portrait variant for the README's narrow-screen picture source."""
    bg, surface, text, muted, border, accent = (
        ("#0B1220", "#101D2E", "#F4F8FB", "#9AAEC1", "#24374A", "#07E3E3")
        if dark else ("#F4F8FB", "#FFFFFF", "#0B1220", "#536A7E", "#D8E5ED", "#007F86")
    )
    colors = [accent, "#648DFF", "#C49BFF", "#E5AF5F", "#7AB8A8", "#8494A4"]
    all_langs = metrics["languages"]
    shown = [dict(entry) for entry in all_langs[:5]]
    if len(all_langs) > 5:
        rest = sum(entry["bytes"] for entry in all_langs[5:])
        shown.append({"name": "Otros", "bytes": rest, "percent": rest / metrics["total_public_code_bytes"] * 100})
    observed = madrid_datetime(metrics["updated_at_utc"])
    date_es = f"{observed.day:02d} {MONTHS_ES[observed.month - 1]} {observed.year}"
    desc = "; ".join(f"{entry['name']}: {entry['percent']:.2f}%" for entry in shown)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="480" height="440" viewBox="0 0 480 440" role="img" aria-labelledby="title desc">',
        '<title id="title">Código público de ' + escape(metrics["username"]) + '</title>',
        '<desc id="desc">' + escape(f"{metrics['public_repositories']} repositorios públicos. Distribución de bytes de código, excluidos forks y perfil: {desc}. Actualizado el {date_es}. No mide experiencia profesional ni dominio de lenguajes.") + '</desc>',
        f'<rect x="1" y="1" width="478" height="438" rx="20" fill="{bg}" stroke="{border}"/>',
        '<g font-family="Arial, Helvetica, sans-serif">',
        f'<text x="28" y="37" fill="{accent}" font-size="16" font-weight="700" letter-spacing="1.5">GITHUB · CÓDIGO PÚBLICO</text>',
        f'<text x="28" y="122" fill="{accent}" font-size="70" font-weight="700">{metrics["public_repositories"]}</text>',
        f'<text x="142" y="94" fill="{text}" font-size="21" font-weight="700">Repositorios públicos</text>',
        f'<text x="142" y="121" fill="{muted}" font-size="17">Incluye este perfil</text>',
        f'<path d="M28 151H452" stroke="{border}"/>',
        f'<text x="28" y="190" fill="{text}" font-size="23" font-weight="700">Lenguajes del código público</text>',
        f'<text x="28" y="217" fill="{muted}" font-size="17">Distribución por bytes</text>',
        '<defs><clipPath id="bar"><rect x="28" y="235" width="424" height="14" rx="7"/></clipPath></defs>',
        f'<rect x="28" y="235" width="424" height="14" rx="7" fill="{surface}"/>',
        '<g clip-path="url(#bar)">',
    ]
    pos = 28.0
    total = metrics["total_public_code_bytes"]
    for i, entry in enumerate(shown):
        width = entry["bytes"] / total * 424 if total else 0
        parts.append(f'<rect x="{pos:.4f}" y="235" width="{width:.4f}" height="14" fill="{colors[i]}"/>')
        pos += width
    parts.append('</g>')
    for i, entry in enumerate(shown):
        x = 28 + (i % 2) * 222
        y = 285 + (i // 2) * 36
        percent = "<0,1 %" if 0 < entry["percent"] < 0.1 else f"{entry['percent']:.1f} %".replace(".", ",")
        name = entry["name"] if len(entry["name"]) < 13 else entry["name"][:11] + "…"
        parts.extend([
            f'<circle cx="{x + 5}" cy="{y - 6}" r="4" fill="{colors[i]}"/>',
            f'<text x="{x + 17}" y="{y}" fill="{text}" font-size="17">{escape(name)}</text>',
            f'<text x="{x + 202}" y="{y}" fill="{muted}" font-size="17" text-anchor="end">{escape(percent)}</text>',
        ])
    if not shown:
        parts.append(f'<text x="28" y="286" fill="{muted}" font-size="17">Sin lenguajes detectados por GitHub.</text>')
    parts.extend([
        f'<path d="M28 381H452" stroke="{border}"/>',
        f'<text x="28" y="405" fill="{muted}" font-size="14">Sin forks ni perfil. No mide dominio.</text>',
        f'<text x="28" y="426" fill="{muted}" font-size="14">Actualizado: {date_es}</text>',
        '</g></svg>',
    ])
    svg = "\n".join(parts) + "\n"
    try:
        ET.fromstring(svg)
    except ET.ParseError:
        raise MetricsError("No se pudo validar la tarjeta móvil. Se conserva el resultado anterior.") from None
    return svg


def write_outputs(metrics, output_dir):
    # Build and validate all output content before creating/replacing any file.
    contents = {
        "metrics-dark.svg": render_svg(metrics, True),
        "metrics-light.svg": render_svg(metrics, False),
        "metrics-mobile-dark.svg": render_mobile_svg(metrics, True),
        "metrics-mobile-light.svg": render_mobile_svg(metrics, False),
        "metrics.json": json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    staged = []
    try:
        for filename, content in contents.items():
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output_dir, prefix=".metrics-", delete=False) as handle:
                staged.append((Path(handle.name), output_dir / filename))
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(handle.name, 0o644)
        for temp_path, final_path in staged:
            os.replace(temp_path, final_path)
    finally:
        for temp_path, _ in staged:
            temp_path.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="AdevTC")
    parser.add_argument("--snapshot", type=Path, help="Snapshot local de respuestas públicas para reproducir una generación.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "assets")
    args = parser.parse_args(argv)
    try:
        if not USERNAME_PATTERN.fullmatch(args.username):
            raise MetricsError("El nombre de usuario de GitHub no es válido.")
        if args.snapshot:
            try:
                snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raise MetricsError("No se pudo leer el snapshot local.") from None
        else:
            snapshot = fetch_snapshot(args.username)
        metrics = aggregate(snapshot, args.username)
        write_outputs(metrics, args.output_dir)
    except (MetricsError, OSError) as exc:
        # Expected errors have safe messages; avoid printing raw OS/network details.
        message = str(exc) if isinstance(exc, MetricsError) else "No se pudo guardar la actualización local."
        print("Error: " + message, file=sys.stderr)
        return 1
    print(f"Actualizadas 4 tarjetas y métricas: {metrics['public_repositories']} repositorios públicos, {len(metrics['languages'])} lenguajes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
