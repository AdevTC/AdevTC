#!/usr/bin/env python3
"""Render public default-branch commit activity, using Python's standard library.

Online:  python3 scripts/update_activity.py --username AdevTC
Offline: python3 scripts/update_activity.py --snapshot /path/to/snapshot.json

This is not GitHub's total contribution calendar. It counts SHA-deduplicated
commits authored by the requested user in public repositories they own,
excluding forks and the profile repository. Dates use the UTC committer date.
The period contains 90 calendar dates, including the partly elapsed last day.
"""

import argparse
from collections import Counter
from datetime import datetime, time, timedelta, timezone
from html import escape
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = "https://api.github.com"
API_VERSION = "2026-03-10"
USERNAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
MONTHS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
WEEKDAYS = ("L", "M", "X", "J", "V", "S", "D")
PALETTES = {
    "dark": {"bg": "#07101F", "panel": "#0D1B2E", "border": "#24354B", "text": "#F1F6FA", "muted": "#9CB1C6", "accent": "#55D9ED", "lime": "#C6F568", "levels": ["#17273B", "#225767", "#258B99", "#55D9ED", "#C6F568"]},
    "light": {"bg": "#F5F9FC", "panel": "#FFFFFF", "border": "#D2DFE9", "text": "#102236", "muted": "#50677C", "accent": "#087F90", "lime": "#587D16", "levels": ["#E3EBF1", "#C2E1E8", "#78C2D0", "#1E98A9", "#6E9623"]},
}


class ActivityError(Exception):
    """A partial or invalid response must not overwrite existing assets."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def parse_datetime(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.astimezone(timezone.utc)
    except (AttributeError, ValueError, TypeError):
        raise ActivityError("Fecha no válida o sin zona horaria.") from None


def iso(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def api_get(path, token="", allow_empty=False):
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": API_VERSION, "User-Agent": "AdevTC-profile-public-activity"}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        with build_opener(NoRedirect).open(Request(API_ROOT + path, headers=headers), timeout=25) as response:
            return json.load(response)
    except HTTPError as exc:
        if allow_empty and exc.code == 409:
            try:
                payload = json.load(exc)
            except (ValueError, OSError):
                payload = {}
            if payload.get("message") == "Git Repository is empty.":
                return None
        raise ActivityError(f"GitHub respondió HTTP {exc.code}; se conservan las tarjetas anteriores.") from None
    except (URLError, TimeoutError, OSError, json.JSONDecodeError):
        raise ActivityError("No se pudo consultar GitHub; se conservan las tarjetas anteriores.") from None


def selected_repositories(repos, username):
    if not isinstance(repos, list):
        raise ActivityError("Falta el listado completo de repositorios.")
    result, seen = [], set()
    for repo in repos:
        if not isinstance(repo, dict):
            raise ActivityError("Repositorio no válido.")
        owner = repo.get("owner", {}).get("login", "")
        name = repo.get("name", "")
        full_name = repo.get("full_name", "")
        if owner.lower() != username.lower() or not name or full_name != owner + "/" + name:
            raise ActivityError("El listado contiene otro propietario o un nombre no válido.")
        if full_name.lower() in seen or repo.get("private") is not False or type(repo.get("fork")) is not bool:
            raise ActivityError("No se ha podido confirmar un listado público sin duplicados.")
        seen.add(full_name.lower())
        if not repo["fork"] and name.lower() != username.lower():
            result.append(repo)
    return result


def fetch_snapshot(username):
    token = os.environ.get("GITHUB_TOKEN", "")
    cutoff = datetime.now(timezone.utc).replace(microsecond=0)
    start = datetime.combine(cutoff.date() - timedelta(days=89), time.min, timezone.utc)
    user_path = "/users/" + quote(username, safe="")
    profile = api_get(user_path, token)
    if str(profile.get("login", "")).lower() != username.lower():
        raise ActivityError("El perfil no corresponde al usuario solicitado.")
    repos = []
    for page in range(1, 1001):
        batch = api_get(user_path + f"/repos?type=owner&sort=full_name&direction=asc&per_page=100&page={page}", token)
        if not isinstance(batch, list):
            raise ActivityError("Listado de repositorios no válido.")
        repos.extend(batch)
        if len(batch) < 100:
            break
    else:
        raise ActivityError("Listado demasiado grande; no se publican resultados parciales.")
    if type(profile.get("public_repos")) is not int or len(repos) != profile["public_repos"]:
        raise ActivityError("El listado de repositorios está incompleto o cambió durante la consulta.")
    selected = selected_repositories(repos, username)
    activity = {}
    for repo in selected:
        branch = repo.get("default_branch")
        if not isinstance(branch, str) or not branch:
            raise ActivityError("No se ha podido identificar la rama por defecto.")
        path = "/repos/" + quote(repo["owner"]["login"], safe="") + "/" + quote(repo["name"], safe="") + "/commits?"
        records, status = [], "ok"
        for page in range(1, 1001):
            query = urlencode({"author": username, "sha": branch, "since": iso(start), "until": iso(cutoff), "per_page": 100, "page": page})
            batch = api_get(path + query, token, allow_empty=True)
            if batch is None:
                if records:
                    raise ActivityError("El repositorio cambió durante la paginación.")
                status = "empty_repository"
                break
            if not isinstance(batch, list):
                raise ActivityError("Listado de commits no válido.")
            for commit in batch:
                try:
                    records.append({"sha": commit["sha"], "author_login": (commit.get("author") or {}).get("login"), "author_date": commit["commit"]["author"]["date"], "committer_date": commit["commit"]["committer"]["date"]})
                except (KeyError, TypeError):
                    raise ActivityError("GitHub devolvió un commit incompleto.") from None
            if len(batch) < 100:
                break
        else:
            raise ActivityError("Demasiados commits; no se publican resultados parciales.")
        activity[repo["full_name"]] = {"status": status, "commits": records, "possibly_more": False, "default_branch": branch}
    return {"retrieved_at_utc": iso(datetime.now(timezone.utc)), "profile": {"login": profile["login"], "public_repos": profile["public_repos"]}, "repos": repos, "activity": {"author": username, "since": iso(start), "until": iso(cutoff), "repository_list_complete": True, "repositories": activity}}


def aggregate(snapshot, username):
    if not isinstance(snapshot, dict) or str(snapshot.get("profile", {}).get("login", "")).lower() != username.lower():
        raise ActivityError("Snapshot no válido para este usuario.")
    activity = snapshot.get("activity", {})
    if activity.get("repository_list_complete") is not True or str(activity.get("author", "")).lower() != username.lower():
        raise ActivityError("El snapshot no confirma un listado completo ni el filtro de autor.")
    observed = parse_datetime(snapshot.get("retrieved_at_utc"))
    cutoff = parse_datetime(activity.get("until"))
    if cutoff > observed or observed > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise ActivityError("La fecha de consulta es incoherente o futura.")
    start_day = cutoff.date() - timedelta(days=89)
    start = datetime.combine(start_day, time.min, timezone.utc)
    if parse_datetime(activity.get("since")) > start:
        raise ActivityError("El snapshot no cubre los 90 días completos.")
    selected = selected_repositories(snapshot.get("repos"), username)
    raw = activity.get("repositories")
    if not isinstance(raw, dict):
        raise ActivityError("Faltan los commits por repositorio.")
    counts, seen, per_repository = Counter(), set(), {}
    for repo in selected:
        name = repo["full_name"]
        result = raw.get(name)
        if not isinstance(result, dict) or result.get("status") not in ("ok", "empty_repository") or result.get("possibly_more") is not False:
            raise ActivityError("Falta una página o un repositorio en el snapshot de actividad.")
        commits = result.get("commits")
        if not isinstance(commits, list) or (result["status"] == "empty_repository" and commits):
            raise ActivityError("Lista de commits incoherente.")
        per_repository[name] = 0
        for commit in commits:
            sha = commit.get("sha", "")
            if not isinstance(sha, str) or not SHA.fullmatch(sha):
                raise ActivityError("SHA de commit no válida.")
            author = commit.get("author_login")
            if author is not None and str(author).lower() != username.lower():
                raise ActivityError("El snapshot contiene un commit de otro autor.")
            timestamp = parse_datetime(commit.get("committer_date"))
            if timestamp < start or timestamp > cutoff:
                continue
            if sha in seen:
                continue
            seen.add(sha)
            counts[timestamp.date().isoformat()] += 1
            per_repository[name] += 1
    days, streak, best = [], 0, 0
    for index in range(90):
        day = start_day + timedelta(days=index)
        count = counts[day.isoformat()]
        streak = streak + 1 if count else 0
        best = max(best, streak)
        days.append({"date": day.isoformat(), "commits": count})
    return {"schema_version": 1, "username": username, "updated_at_utc": iso(cutoff), "retrieved_at_utc": iso(observed), "period": {"start_date_utc": start_day.isoformat(), "end_date_utc": cutoff.date().isoformat(), "calendar_days": 90, "last_day_partial": True}, "scope": f"Commits públicos de autor {username} en ramas por defecto de repositorios propios, sin forks ni perfil; SHA deduplicadas. Incluye merges. No son contribuciones totales de GitHub. Días y rachas por fecha UTC del committer.", "total_commits": len(seen), "active_days": sum(day["commits"] > 0 for day in days), "best_streak_days_in_period": best, "repositories_checked": len(selected), "active_repositories": sum(count > 0 for count in per_repository.values()), "commits_by_repository": per_repository, "days": days}


def date_es(value, with_year=False):
    day = datetime.fromisoformat(value).date()
    return f"{day.day} {MONTHS[day.month - 1]}" + (f" {day.year}" if with_year else "")


def level(count):
    return 0 if count == 0 else 1 if count <= 2 else 2 if count <= 5 else 3 if count <= 10 else 4


def render(data, theme, mobile=False):
    colors = PALETTES[theme]
    width, height = (640, 780) if mobile else (1200, 560)
    title = "Commits públicos · 90 días"
    period = date_es(data["period"]["start_date_utc"]) + " — " + date_es(data["period"]["end_date_utc"], True)
    description = f'{data["total_commits"]} commits; {data["active_days"]} días activos; mejor racha del periodo: {data["best_streak_days_in_period"]} días. {period}. Solo repositorios públicos propios, ramas por defecto, sin forks ni perfil. No son las contribuciones totales de GitHub.'
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">', f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>', f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="26" fill="{colors["bg"]}" stroke="{colors["border"]}"/>', '<g font-family="Arial, Helvetica, sans-serif">']
    def text(x, y, value, size=16, color="text", weight=400, extra=""):
        parts.append(f'<text x="{x}" y="{y}" fill="{colors[color]}" font-size="{size}" font-weight="{weight}" {extra}>{escape(str(value))}</text>')
    text(36, 38, "GITHUB  /  ACTIVIDAD PÚBLICA", 12, "accent", 700, 'letter-spacing="2"')
    text(36, 82, title, 32 if mobile else 36, "text", 700)
    text(36, 112, period + " · UTC", 16, "muted")
    if mobile:
        kpi_y, kpi_w, gap = 139, 176, 20
        for i, (value, label) in enumerate([(data["total_commits"], "Commits"), (data["active_days"], "Días activos"), (data["best_streak_days_in_period"], "Mejor racha")]):
            x = 36 + i * (kpi_w + gap)
            parts.append(f'<rect x="{x}" y="{kpi_y}" width="{kpi_w}" height="118" rx="16" fill="{colors["panel"]}" stroke="{colors["border"]}"/>')
            text(x+20, kpi_y+58, value, 44, "accent" if i != 2 else "lime", 700)
            text(x+20, kpi_y+89, label, 16, "muted")
        grid_x, grid_y, cell, gap = 76, 326, 32, 6
        text(36, 296, "DÍAS CON COMMITS", 12, "muted", 700, 'letter-spacing="1.5"')
    else:
        kpi_y, kpi_w = 146, 176
        for i, (value, label) in enumerate([(data["total_commits"], "Commits"), (data["active_days"], "Días activos"), (data["best_streak_days_in_period"], "Mejor racha")]):
            x = 36 + i * (kpi_w + 18)
            parts.append(f'<rect x="{x}" y="{kpi_y}" width="{kpi_w}" height="110" rx="16" fill="{colors["panel"]}" stroke="{colors["border"]}"/>')
            text(x+20, kpi_y+54, value, 42, "accent" if i != 2 else "lime", 700)
            text(x+20, kpi_y+84, label, 16, "muted")
        grid_x, grid_y, cell, gap = 672, 171, 28, 7
        text(636, 141, "DÍAS CON COMMITS", 12, "muted", 700, 'letter-spacing="1.5"')
    start_day = datetime.fromisoformat(data["period"]["start_date_utc"]).date()
    for row in range(7):
        text(grid_x-21, grid_y+row*(cell+gap)+cell*0.7, WEEKDAYS[(start_day.weekday()+row)%7], 12, "muted", 400, 'text-anchor="middle"')
    for index, day in enumerate(data["days"]):
        column, row = divmod(index, 7)
        x, y = grid_x + column*(cell+gap), grid_y + row*(cell+gap)
        fill = colors["levels"][level(day["commits"])]
        parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="5" fill="{fill}"><title>{day["date"]}: {day["commits"]} commits</title></rect>')
    label_y = grid_y - 13
    for column in (0, 4, 8, 12):
        label_day = start_day + timedelta(days=7*column)
        text(grid_x+column*(cell+gap), label_y, f'{label_day.day}/{label_day.month:02}', 11, "muted")
    legend_y = grid_y + 7*(cell+gap) + 17
    for i, label in enumerate(("0", "1–2", "3–5", "6–10", "11+")):
        x = grid_x + 25 + i*74
        parts.append(f'<rect x="{x}" y="{legend_y-13}" width="14" height="14" rx="3" fill="{colors["levels"][i]}"/>')
        text(x+21, legend_y-1, label, 11, "muted")
    if mobile:
        parts.append(f'<path d="M36 668H604" stroke="{colors["border"]}"/>')
        text(36, 698, "Repositorios propios · ramas por defecto", 16, "text", 700)
        text(36, 725, "Sin forks ni perfil · UTC · último día parcial", 15, "muted")
        text(36, 752, "Actualizado: " + date_es(data["updated_at_utc"], True), 14, "accent")
    else:
        text(36, 306, "Código público, día a día.", 25, "text", 700)
        text(36, 338, "Actividad en mis repositorios y sus ramas por defecto.", 16, "muted")
        text(36, 367, "Sin forks ni el repositorio de este perfil.", 16, "muted")
        text(36, 398, "La racha se calcula dentro de este periodo.", 14, "muted")
        parts.append(f'<path d="M36 474H1164" stroke="{colors["border"]}"/>')
        text(36, 510, "No equivale al total de contribuciones de GitHub. Último día parcial.", 14, "muted")
        text(1164, 510, "Actualizado: " + date_es(data["updated_at_utc"], True), 14, "accent", 400, 'text-anchor="end"')
    parts += ['</g>', '</svg>']
    svg = "\n".join(parts) + "\n"
    ET.fromstring(svg)
    return svg


def write_outputs(data, output_dir):
    payloads = {"activity.json": json.dumps(data, ensure_ascii=False, indent=2) + "\n"}
    for theme in ("dark", "light"):
        payloads[f"activity-{theme}.svg"] = render(data, theme)
        payloads[f"activity-mobile-{theme}.svg"] = render(data, theme, True)
    output_dir.mkdir(parents=True, exist_ok=True)
    staged = []
    try:
        for name, content in payloads.items():
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output_dir, delete=False) as temp:
                temp.write(content)
                staged.append((Path(temp.name), output_dir / name))
        for temporary, target in staged:
            temporary.replace(target)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="AdevTC")
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "assets")
    args = parser.parse_args()
    if not USERNAME.fullmatch(args.username):
        parser.error("Nombre de usuario no válido")
    try:
        if args.snapshot:
            snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        else:
            snapshot = fetch_snapshot(args.username)
        data = aggregate(snapshot, args.username)
        write_outputs(data, args.output_dir)
        print(f'Actividad pública: {data["total_commits"]} commits, {data["active_days"]} días activos, mejor racha {data["best_streak_days_in_period"]} días. Actualizado {data["updated_at_utc"]}.')
    except (ActivityError, OSError, json.JSONDecodeError) as exc:
        print("No se actualizó la actividad: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
