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
import math
import os
from pathlib import Path
import re
import shutil
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
        owner_data = repo.get("owner")
        if not isinstance(owner_data, dict):
            raise MetricsError("Falta el propietario de un repositorio.")
        owner = owner_data.get("login", "")
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


def optional_count(record, name):
    """Missing social fields are unknown, never an invented zero."""
    value = record.get(name)
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise MetricsError("GitHub devolvió un contador no válido: " + name + ".")
    return value


def sum_optional_counts(records, name):
    values = [optional_count(record, name) for record in records]
    return None if any(value is None for value in values) else sum(values)


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
    profile = snapshot["profile"]
    original_repos = [repo for repo in snapshot["repos"] if not repo["fork"]]
    stars = sum_optional_counts(original_repos, "stargazers_count")
    received_forks = sum_optional_counts(original_repos, "forks_count")
    followers = optional_count(profile, "followers")
    following = optional_count(profile, "following")
    return {
        "schema_version": 2,
        "username": snapshot["profile"]["login"],
        "updated_at_utc": observed.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "public_repositories": profile["public_repos"],
        "nonfork_public_repositories": len(original_repos),
        "stars_received": stars,
        "forks_received": received_forks,
        "followers": followers,
        "following": following,
        "engagement_scope": {
            "description": "Stars y forks recibidos en todos los repositorios públicos propios no fork, incluido el perfil.",
            "repositories_counted": len(original_repos),
            "excluded_forks": forks,
        },
        "data_availability": {
            "stars_received": stars is not None,
            "forks_received": received_forks is not None,
            "followers": followers is not None,
            "following": following is not None,
        },
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



def palette(dark):
    return {
        "bg": "#07101f" if dark else "#f3f7fc",
        "surface": "#0d1b2d" if dark else "#ffffff",
        "text": "#edf5fc" if dark else "#10243b",
        "muted": "#9cacc1" if dark else "#52677f",
        "border": "#203047" if dark else "#d5dfeb",
        "cyan": "#55d9ed" if dark else "#007d94",
        "lime": "#c6f568" if dark else "#567700",
        "violet": "#b9a5ff" if dark else "#7251b3",
        "rose": "#f7a5c6" if dark else "#b54e79",
        "gold": "#f2c76d" if dark else "#986510",
        "blue": "#83afff" if dark else "#316dd3",
        "other": "#65758c" if dark else "#8c9bb0",
    }


def format_count(value):
    if value is None:
        return "N/D"
    if value < 1000:
        return str(value)
    if value < 1000000:
        return (f"{value / 1000:.1f}".rstrip("0").rstrip(".") + "k").replace(".", ",")
    return (f"{value / 1000000:.1f}".rstrip("0").rstrip(".") + "M").replace(".", ",")


def format_bytes(value):
    if value >= 1000000:
        return f"{value / 1000000:.1f} MB".replace(".", ",")
    if value >= 1000:
        return f"{value / 1000:.1f} kB".replace(".", ",")
    return str(value) + " B"


def format_percent(value):
    return "<0,1 %" if 0 < value < 0.1 else f"{value:.1f} %".replace(".", ",")


def date_label(metrics):
    observed = madrid_datetime(metrics["updated_at_utc"])
    return f"{observed.day:02d} {MONTHS_ES[observed.month - 1]} {observed.year}"


def short_text(value, max_chars):
    return value if len(value) <= max_chars else value[:max_chars - 1] + "…"


def svg_start(width, height, title, description, p):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">' + escape(title) + '</title>',
        '<desc id="desc">' + escape(description) + '</desc>',
        f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="24" fill="{p["bg"]}" stroke="{p["border"]}"/>',
        '<g font-family="Arial, Helvetica, sans-serif">',
    ]


def svg_finish(parts):
    svg = "\n".join(parts + ["</g></svg>"]) + "\n"
    try:
        ET.fromstring(svg)
    except ET.ParseError:
        raise MetricsError("No se pudo validar una tarjeta SVG. Se conservan las tarjetas anteriores.") from None
    return svg


def icon(kind, x, y, color, size=25):
    paths = {
        "repo": '<path d="M5 3h14v17H7a2 2 0 0 1-2-2V3Zm0 13h14M9 7h6M9 10h4"/>',
        "star": '<path d="m12 3 2.8 5.7 6.3.9-4.5 4.4 1.1 6.3-5.7-3-5.7 3 1.1-6.3L3 9.6l6.3-.9Z"/>',
        "fork": '<circle cx="6" cy="4" r="2"/><circle cx="18" cy="4" r="2"/><circle cx="12" cy="20" r="2"/><path d="M6 6v3a6 6 0 0 0 6 6m6-9v3a6 6 0 0 1-6 6v3"/>',
        "users": '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3m1-16a3 3 0 0 1 0 6m2 3a5 5 0 0 1 3 4v3"/>',
        "code": '<path d="m7 6-5 6 5 6m10-12 5 6-5 6m-3-15-4 18"/>',
        "langs": '<path d="M5 5h14M8 2v6m9-3c-1 6-5 10-12 12m2-8c2 4 5 6 9 7m-1 5 3-8 3 8m-5-3h4"/>',
    }
    return f'<g transform="translate({x} {y}) scale({size/24:.5f})" fill="none" stroke="{color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{paths[kind]}</g>'


def metric_tiles(metrics):
    scope = metrics["language_scope"]
    following = format_count(metrics.get("following"))
    return [
        ("repo", metrics["public_repositories"], "Repositorios", "públicos", "cyan"),
        ("star", metrics.get("stars_received"), "Stars recibidas", "repos propios · sin forks", "lime"),
        ("fork", metrics.get("forks_received"), "Forks recibidos", "repos propios · sin forks", "violet"),
        ("users", metrics.get("followers"), "Seguidores", "Siguiendo a " + following, "cyan"),
        ("code", scope["repositories_with_detected_code"], "Repos con código", "sin forks ni perfil", "lime"),
        ("langs", len(metrics["languages"]), "Lenguajes", "detectados por GitHub", "violet"),
    ]


def render_dashboard(metrics, dark, mobile=False):
    p = palette(dark)
    width, height = (640, 620) if mobile else (1200, 330)
    date = date_label(metrics)
    readable = "; ".join(
        f"{label}: {value if value is not None else 'no disponible'}"
        for _, value, label, _, _ in metric_tiles(metrics)
    )
    description = (
        f"Estadísticas públicas de {metrics['username']}. {readable}. "
        f"Siguiendo: {metrics.get('following') if metrics.get('following') is not None else 'no disponible'}. "
        "Repositorios incluye forks y perfil. Stars y forks recibidos solo en repositorios propios no fork, incluido el perfil. "
        "Código y lenguajes excluyen forks y perfil. N/D significa que el dato no estaba disponible. "
        f"Datos consultados el {date}."
    )
    parts = svg_start(width, height, "GitHub en números · " + metrics["username"], description, p)
    left = 28 if mobile else 32
    parts += [
        f'<text x="{left}" y="33" fill="{p["cyan"]}" font-size="{14 if mobile else 12}" font-weight="700" letter-spacing="2">{escape(metrics["username"])} / GITHUB</text>',
        f'<text x="{left}" y="68" fill="{p["text"]}" font-size="{32 if mobile else 29}" font-weight="700">GitHub en números.</text>',
    ]
    if mobile:
        parts.append(f'<text x="612" y="33" text-anchor="end" fill="{p["muted"]}" font-size="13">{date}</text>')
    else:
        parts += [
            f'<text x="1168" y="37" text-anchor="end" fill="{p["muted"]}" font-size="12">DATOS PÚBLICOS</text>',
            f'<text x="1168" y="61" text-anchor="end" fill="{p["text"]}" font-size="14">{date}</text>',
        ]
    for i, (kind, value, label, subtitle, accent) in enumerate(metric_tiles(metrics)):
        if mobile:
            x, y, w, h = 28 + (i % 2) * 300, 99 + (i // 2) * 150, 284, 134
        else:
            x, y, w, h = 32 + (i % 3) * 384, 92 + (i // 3) * 106, 368, 94
        parts += [
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{p["surface"]}" stroke="{p["border"]}"/>',
            f'<path d="M{x+18} {y+1}H{x+55}" stroke="{p[accent]}" stroke-width="2" stroke-linecap="round"/>',
        ]
        if mobile:
            parts += [
                icon(kind, x+w-45, y+20, p[accent], 25),
                f'<text x="{x+20}" y="{y+61}" fill="{p[accent]}" font-size="49" font-weight="700">{format_count(value)}</text>',
                f'<text x="{x+20}" y="{y+94}" fill="{p["text"]}" font-size="19" font-weight="700">{escape(label)}</text>',
                f'<text x="{x+20}" y="{y+118}" fill="{p["muted"]}" font-size="14">{escape(subtitle)}</text>',
            ]
        else:
            parts += [
                icon(kind, x+w-36, y+15, p[accent], 19),
                f'<text x="{x+20}" y="{y+64}" fill="{p[accent]}" font-size="45" font-weight="700">{format_count(value)}</text>',
                f'<text x="{x+124}" y="{y+41}" fill="{p["text"]}" font-size="17" font-weight="700">{escape(label)}</text>',
                f'<text x="{x+124}" y="{y+64}" fill="{p["muted"]}" font-size="12">{escape(subtitle)}</text>',
            ]
    if mobile:
        parts += [
            f'<path d="M28 557H612" stroke="{p["border"]}"/>',
            f'<text x="28" y="580" fill="{p["muted"]}" font-size="13">Repos públicos · Stars y forks de repos originales.</text>',
            f'<text x="28" y="601" fill="{p["muted"]}" font-size="13">Código sin forks ni perfil · N/D: dato no disponible.</text>',
        ]
    else:
        parts.append(f'<text x="32" y="316" fill="{p["muted"]}" font-size="12">Repos públicos · Stars y forks de repos originales · Código sin forks ni perfil · N/D: no disponible</text>')
    return svg_finish(parts)


def render_svg(metrics, dark):
    """Desktop dashboard; kept compatible with the original public helper."""
    return render_dashboard(metrics, dark, mobile=False)


def render_mobile_svg(metrics, dark):
    return render_dashboard(metrics, dark, mobile=True)


def render_languages_svg(metrics, dark, mobile=False):
    p = palette(dark)
    width, height = (640, 500) if mobile else (1200, 300)
    colors = [p[k] for k in ("cyan", "lime", "violet", "blue", "rose", "gold")]
    total = metrics["total_public_code_bytes"]
    all_langs = metrics["languages"]
    shown = all_langs[:6]
    other_bytes = sum(item["bytes"] for item in all_langs[6:])
    date = date_label(metrics)
    description = (
        f"Distribución de {total} bytes de código público de {metrics['username']}. "
        + "; ".join(f"{item['name']}: {item['percent']:.4f} %" for item in all_langs)
        + ". Se excluyen forks y repositorio de perfil; se incluyen archivados. "
        "Los porcentajes describen código, no dominio de tecnologías. "
        f"Fecha de consulta: {date}."
    )
    parts = svg_start(width, height, "Lenguajes del código público · " + metrics["username"], description, p)
    left = 28 if mobile else 32
    parts += [
        f'<text x="{left}" y="33" fill="{p["cyan"]}" font-size="{13 if mobile else 12}" font-weight="700" letter-spacing="1.8">LENGUAJES / POR BYTES</text>',
        f'<text x="{left}" y="68" fill="{p["text"]}" font-size="{32 if mobile else 29}" font-weight="700">El código, por dentro.</text>',
        f'<text x="{width-left}" y="33" text-anchor="end" fill="{p["muted"]}" font-size="13">TOP {min(6,len(all_langs))} / {len(all_langs)}</text>',
    ]
    cx, cy, radius, stroke = (320, 184, 77, 18) if mobile else (150, 172, 76, 19)
    circumference = math.tau * radius
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="{p["border"]}" stroke-width="{stroke}"/>')
    segments = [(item["bytes"], colors[i]) for i, item in enumerate(shown)]
    if other_bytes:
        segments.append((other_bytes, p["other"]))
    offset = 0.0
    for amount, color in segments:
        length = amount / total * circumference if total else 0.0
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="{color}" stroke-width="{stroke}" '
            f'stroke-dasharray="{length:.6f} {max(0.0,circumference-length):.6f}" stroke-dashoffset="{-offset:.6f}" '
            f'transform="rotate(-90 {cx} {cy})"/>'
        )
        offset += length
    parts += [
        f'<text x="{cx}" y="{cy-9}" text-anchor="middle" fill="{p["muted"]}" font-size="12" letter-spacing="1.5">CÓDIGO</text>',
        f'<text x="{cx}" y="{cy+23}" text-anchor="middle" fill="{p["text"]}" font-size="25" font-weight="700">{format_bytes(total)}</text>',
    ]
    for i, item in enumerate(shown):
        if mobile:
            x, y, w = 28 + (i % 2) * 300, 306 + (i // 2) * 59, 284
            label_size, value_size, max_chars = 18, 17, 14
        else:
            x, y, w = 293 + (i % 2) * 449, 115 + (i // 2) * 59, 416
            label_size, value_size, max_chars = 18, 17, 26
        name = short_text(item["name"], max_chars)
        percent = item["bytes"] / total * 100 if total else 0
        parts += [
            f'<circle cx="{x+5}" cy="{y-6}" r="4.5" fill="{colors[i]}"/>',
            f'<text x="{x+19}" y="{y}" fill="{p["text"]}" font-size="{label_size}" font-weight="700">{escape(name)}</text>',
            f'<text x="{x+w}" y="{y}" text-anchor="end" fill="{p["muted"]}" font-size="{value_size}">{escape(format_percent(percent))}</text>',
            f'<rect x="{x}" y="{y+11}" width="{w}" height="5" rx="2.5" fill="{p["border"]}"/>',
            f'<rect x="{x}" y="{y+11}" width="{max(0.7, w*percent/100):.4f}" height="5" rx="2.5" fill="{colors[i]}"/>',
        ]
    if not shown:
        parts += [
            f'<text x="{320 if mobile else 293}" y="{325 if mobile else 150}" fill="{p["muted"]}" font-size="19" text-anchor="{"middle" if mobile else "start"}">Sin lenguajes detectados.</text>',
            f'<text x="{320 if mobile else 293}" y="{352 if mobile else 178}" fill="{p["muted"]}" font-size="15" text-anchor="{"middle" if mobile else "start"}">GitHub no informa bytes de código.</text>',
        ]
    tail = f" · Otros: {format_percent(other_bytes / total * 100)}" if other_bytes and total else ""
    if mobile:
        parts += [
            f'<path d="M28 457H612" stroke="{p["border"]}"/>',
            f'<text x="28" y="478" fill="{p["muted"]}" font-size="12">Sin forks ni perfil · Incluye archivados{escape(tail)}</text>',
            f'<text x="28" y="494" fill="{p["muted"]}" font-size="12">Consulta: {date} · Por bytes, no por nivel de dominio.</text>',
        ]
    else:
        parts += [
            f'<path d="M32 263H1168" stroke="{p["border"]}"/>',
            f'<text x="32" y="286" fill="{p["muted"]}" font-size="12">Sin forks ni perfil · Incluye archivados · Por bytes, no por dominio{escape(tail)}</text>',
            f'<text x="1168" y="286" text-anchor="end" fill="{p["muted"]}" font-size="12">{date}</text>',
        ]
    return svg_finish(parts)


def validate_metrics(metrics):
    """Also accepts the prior schema-1 aggregate for an honest dated seed."""
    if not isinstance(metrics, dict) or not USERNAME_PATTERN.fullmatch(str(metrics.get("username", ""))):
        raise MetricsError("El agregado no identifica un usuario válido.")
    for key in ("public_repositories", "total_public_code_bytes"):
        if type(metrics.get(key)) is not int or metrics[key] < 0:
            raise MetricsError("Falta un contador válido en el agregado.")
    for key in ("stars_received", "forks_received", "followers", "following"):
        optional_count(metrics, key)
    try:
        date_label(metrics)
    except (KeyError, TypeError, ValueError):
        raise MetricsError("Falta una fecha válida en el agregado.") from None
    scope = metrics.get("language_scope")
    if not isinstance(scope, dict):
        raise MetricsError("Falta el ámbito de lenguajes.")
    for key in ("repositories_queried", "repositories_with_detected_code"):
        if type(scope.get(key)) is not int or scope[key] < 0:
            raise MetricsError("El ámbito de lenguajes no está completo.")
    if not scope["repositories_with_detected_code"] <= scope["repositories_queried"] <= metrics["public_repositories"]:
        raise MetricsError("Los contadores de repositorios no coinciden.")
    langs = metrics.get("languages")
    if not isinstance(langs, list):
        raise MetricsError("Falta la distribución de lenguajes.")
    seen, total = set(), metrics["total_public_code_bytes"]
    for item in langs:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip() or len(item["name"]) > 80:
            raise MetricsError("Hay un lenguaje no válido en el agregado.")
        if item["name"] in seen or type(item.get("bytes")) is not int or item["bytes"] <= 0:
            raise MetricsError("Hay un tamaño o lenguaje duplicado en el agregado.")
        seen.add(item["name"])
        percent = item.get("percent")
        if type(percent) not in (int, float) or not math.isfinite(percent) or total == 0 or abs(percent - item["bytes"] / total * 100) > 0.00001:
            raise MetricsError("Los porcentajes no corresponden a los bytes de código.")
    if sum(item["bytes"] for item in langs) != total:
        raise MetricsError("La distribución de lenguajes está incompleta.")


def write_outputs(metrics, output_dir):
    # Finish every API validation and SVG render before touching prior outputs.
    validate_metrics(metrics)
    contents = {
        "metrics-dark.svg": render_svg(metrics, True),
        "metrics-light.svg": render_svg(metrics, False),
        "metrics-mobile-dark.svg": render_mobile_svg(metrics, True),
        "metrics-mobile-light.svg": render_mobile_svg(metrics, False),
        "languages-dark.svg": render_languages_svg(metrics, True),
        "languages-light.svg": render_languages_svg(metrics, False),
        "languages-mobile-dark.svg": render_languages_svg(metrics, True, mobile=True),
        "languages-mobile-light.svg": render_languages_svg(metrics, False, mobile=True),
        "metrics.json": json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
    }
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_dir, prefix=".metrics-stage-") as temporary:
        stage = Path(temporary)
        staged, backups, replaced = {}, {}, []
        for filename, content in contents.items():
            path = stage / filename
            with path.open("w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            path.chmod(0o644)
            staged[filename] = path
            destination = output_dir / filename
            if destination.exists():
                backup = stage / (filename + ".previous")
                shutil.copy2(destination, backup)
                backups[filename] = backup
        try:
            for filename, path in staged.items():
                os.replace(path, output_dir / filename)
                replaced.append(filename)
        except OSError:
            # Restore the previous complete set if a local replacement fails.
            for filename in reversed(replaced):
                destination = output_dir / filename
                if filename in backups:
                    os.replace(backups[filename], destination)
                else:
                    destination.unlink(missing_ok=True)
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="AdevTC")
    parser.add_argument("--snapshot", type=Path, help="Snapshot local completo de respuestas públicas para reproducir la generación.")
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
        message = str(exc) if isinstance(exc, MetricsError) else "No se pudo guardar la actualización local."
        print("Error: " + message, file=sys.stderr)
        return 1
    print(
        f"Actualizadas 8 tarjetas y métricas: {metrics['public_repositories']} repositorios públicos, "
        f"{len(metrics['languages'])} lenguajes, stars={format_count(metrics.get('stars_received'))}, "
        f"seguidores={format_count(metrics.get('followers'))}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

