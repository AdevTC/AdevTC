#!/usr/bin/env python3
"""Regenera los SVG de marca. Solo usa la biblioteca estándar de Python."""

from html import escape
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)


def write(name, width, height, title, body):
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">
<title id="title">{escape(title)}</title>
{body}
</svg>
'''
    (ASSETS / name).write_text(svg, encoding="utf-8")


for theme in ("dark", "light"):
    dark = theme == "dark"
    bg = "#0B1220" if dark else "#F4F8FB"
    fg = "#F7FAFC" if dark else "#10283E"
    dim = "#9AABBF" if dark else "#4C6377"
    cyan = "#07E3E3" if dark else "#007F86"
    line = "#22354B" if dark else "#CDDFE8"
    panel = "#111E30" if dark else "#E6F1F5"

    dots = "\n".join(
        f'<circle cx="{x}" cy="{y}" r="1.2" fill="{line}" />'
        for x in range(814, 1250, 28) for y in range(74, 420, 28)
    )
    write(f"header-{theme}.svg", 1280, 464,
          "Adrián Tomás Cerdá. Conecto sistemas. Construyo soluciones.", f'''
<defs>
 <linearGradient id="wash" x1="0" y1="0" x2="1" y2="1">
  <stop stop-color="{panel}" /><stop offset="1" stop-color="{bg}" />
 </linearGradient>
 <linearGradient id="signal" x1="0" x2="1">
  <stop stop-color="{cyan}" stop-opacity="0" /><stop offset="0.5" stop-color="{cyan}" /><stop offset="1" stop-color="{cyan}" stop-opacity="0" />
 </linearGradient>
</defs>
<rect x="1" y="1" width="1278" height="462" rx="28" fill="{bg}" stroke="{line}" stroke-width="2" />
<path d="M780 1H1252Q1279 1 1279 28V436Q1279 463 1252 463H930Z" fill="url(#wash)" />
{dots}
<g font-family="Arial, Helvetica, sans-serif">
 <g fill="none" stroke="{cyan}" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round">
  <path d="M62 45L50 56L62 67M80 45L92 56L80 67M75 43L67 69" />
 </g>
 <text x="110" y="64" fill="{fg}" font-size="25" font-weight="700" letter-spacing="3">ADEVTC</text>
 <text x="1208" y="62" fill="{dim}" font-size="18" text-anchor="end" letter-spacing="2">MADRID, ES</text>
 <path d="M50 91H1230" stroke="{line}" />
 <text x="60" y="145" fill="{cyan}" font-size="17" font-weight="700" letter-spacing="3.2">SAP INTEGRATION &amp; SOFTWARE DEVELOPMENT</text>
 <text x="55" y="239" fill="{fg}" font-size="100" font-weight="700" letter-spacing="-4">Adrián</text>
 <text x="55" y="329" fill="{fg}" font-size="88" font-weight="700" letter-spacing="-3.4">Tomás Cerdá<tspan fill="{cyan}">.</tspan></text>
 <text x="60" y="377" fill="{dim}" font-size="25">Conecto sistemas. Construyo soluciones.</text>
 <circle cx="66" cy="424" r="5" fill="{cyan}" />
 <text x="83" y="430" fill="{dim}" font-size="16" letter-spacing="2">SAP BTP  /  INTEGRATION SUITE  /  FULL STACK</text>
</g>
<g fill="none" stroke="{line}" stroke-width="2">
 <circle cx="1030" cy="265" r="139" />
 <circle cx="1030" cy="265" r="108" stroke-dasharray="4 12" />
 <path d="M831 190H885L932 237M1129 294L1175 340H1230M1047 126V171M920 337L877 380H817" />
</g>
<path d="M891 265A139 139 0 0 1 1030 126" fill="none" stroke="{cyan}" stroke-width="3" />
<path d="M1065 400A139 139 0 0 0 1166 294" fill="none" stroke="{cyan}" stroke-width="3" opacity="0.4" />
<g font-family="Arial, Helvetica, sans-serif">
 <rect x="949" y="185" width="162" height="162" rx="35" fill="{panel}" stroke="{cyan}" stroke-width="1.5" />
 <path d="M979 233L965 247L979 261M1081 233L1095 247L1081 261" fill="none" stroke="{cyan}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
 <text x="1030" y="272" text-anchor="middle" font-size="52" font-weight="700" fill="{fg}" letter-spacing="-3">AT</text>
 <text x="1030" y="314" text-anchor="middle" font-size="11" font-weight="700" letter-spacing="3" fill="{dim}">BUILD · CONNECT</text>
 <rect x="801" y="170" width="96" height="39" rx="11" fill="{bg}" stroke="{line}" />
 <text x="849" y="196" text-anchor="middle" font-size="17" font-weight="700" fill="{fg}">SAP</text>
 <rect x="1116" y="319" width="103" height="39" rx="11" fill="{bg}" stroke="{line}" />
 <text x="1167" y="345" text-anchor="middle" font-size="17" font-weight="700" fill="{fg}">WEB</text>
 <circle cx="1047" cy="128" r="5" fill="{cyan}" />
 <circle cx="817" cy="380" r="5" fill="{cyan}" />
</g>
''')

    write(f"header-mobile-{theme}.svg", 640, 470,
          "Adrián Tomás Cerdá. Conecto sistemas. Construyo soluciones.", f'''
<rect x="1" y="1" width="638" height="468" rx="24" fill="{bg}" stroke="{line}" stroke-width="2" />
<path d="M444 1H616Q639 1 639 24V446Q639 469 616 469H576Z" fill="{panel}" />
<g font-family="Arial, Helvetica, sans-serif">
 <path d="M43 37L32 47L43 57M61 37L72 47L61 57M56 35L48 59" fill="none" stroke="{cyan}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
 <text x="90" y="55" fill="{fg}" font-size="25" font-weight="700" letter-spacing="2">ADEVTC</text>
 <text x="606" y="53" fill="{dim}" font-size="16" text-anchor="end" letter-spacing="1">MADRID, ES</text>
 <path d="M32 83H608" stroke="{line}" />
 <text x="34" y="131" fill="{cyan}" font-size="20" font-weight="700" letter-spacing="2">SAP BTP / FULL STACK</text>
 <text x="30" y="226" fill="{fg}" font-size="97" font-weight="700" letter-spacing="-4">Adrián</text>
 <text x="30" y="306" fill="{fg}" font-size="74" font-weight="700" letter-spacing="-3">Tomás Cerdá<tspan fill="{cyan}">.</tspan></text>
 <text x="35" y="365" fill="{dim}" font-size="28">Conecto sistemas.</text>
 <text x="35" y="404" fill="{dim}" font-size="28">Construyo soluciones.</text>
 <path d="M36 437H116" stroke="{cyan}" stroke-width="3" stroke-linecap="round" />
 <circle cx="134" cy="437" r="4" fill="{cyan}" />
</g>''')

    write(f"footer-{theme}.svg", 1280, 110,
          "AdevTC. De la idea a la integración. Del código a la experiencia.", f'''
<rect x="1" y="1" width="1278" height="108" rx="18" fill="{bg}" stroke="{line}" />
<rect x="32" y="34" width="4" height="42" rx="2" fill="{cyan}" />
<g font-family="Arial, Helvetica, sans-serif">
 <text x="57" y="64" font-size="23" font-weight="700" letter-spacing="2" fill="{fg}">ADEVTC</text>
 <text x="1230" y="64" text-anchor="end" font-size="23" fill="{dim}">De la idea a la integración. Del código a la experiencia.</text>
</g>''')


links = [
    ("portfolio", "PORTFOLIO", 168, "#07E3E3", "#06232B", 'M22 13H38V27H22ZM22 17H38M26 13V27'),
    ("linkedin", "LINKEDIN", 158, "#15243A", "#F4F8FC", 'M23 19V29M23 14V14.2M29 29V19M29 23C29 18 37 18 37 23V29'),
    ("email", "EMAIL", 138, "#15243A", "#F4F8FC", 'M21 14H39V28H21ZM21 15L30 22L39 15'),
]
for name, label, width, bg, fg, icon in links:
    write(f"link-{name}.svg", width, 40, label, f'''
<rect x="0.5" y="0.5" width="{width-1}" height="39" rx="10" fill="{bg}" stroke="#355068" />
<path d="{icon}" fill="none" stroke="{fg}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" />
<text x="51" y="25.5" fill="{fg}" font-family="Arial, Helvetica, sans-serif" font-size="12" font-weight="700" letter-spacing="1.1">{label}</text>''')

tech = [
    ("typescript", "TypeScript", 120, "#54A5FF"),
    ("react", "React", 84, "#61DAFB"),
    ("nextjs", "Next.js", 94, "#F7FAFC"),
    ("angular", "Angular", 104, "#FF6697"),
    ("tailwind", "Tailwind CSS", 137, "#38BDF8"),
    ("nodejs", "Node.js", 102, "#8FD46A"),
    ("java", "Java", 77, "#F5AE65"),
    ("spring", "Spring Boot", 134, "#8FD46A"),
]
for name, label, width, color in tech:
    write(f"tech-{name}.svg", width, 30, label, f'''
<rect x="0.5" y="0.5" width="{width-1}" height="29" rx="7" fill="#111E30" stroke="#355068" />
<circle cx="15" cy="15" r="3.5" fill="{color}" />
<text x="27" y="19.7" fill="#F2F7FC" font-family="Arial, Helvetica, sans-serif" font-size="13" font-weight="600">{label}</text>''')

print("Brand assets generated in assets/.")
