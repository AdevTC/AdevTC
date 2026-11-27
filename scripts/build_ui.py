#!/usr/bin/env python3
"""Build small, self-contained SVG controls for AdevTC's GitHub profile.

Run with Python 3. Links belong in README.md around each image; SVGs contain no
scripts, external fonts, network dependencies, or embedded hyperlinks.
"""

from pathlib import Path
from html import escape
from math import ceil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets' / 'ui'
SANS = "'Segoe UI',Arial,sans-serif"
MONO = "'SFMono-Regular',Consolas,'Liberation Mono',monospace"
NAVY = '#07101f'
PANEL = '#0c1a2c'
WHITE = '#f1f5fb'
SLATE = '#98acc2'
CYAN = '#55d9ed'
LIME = '#c6f568'
VIOLET = '#b9a5ff'


def text(x, y, value, size, fill=WHITE, weight=500, extra='', mono=False):
    return (f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" '
            f'font-weight="{weight}" font-family="{MONO if mono else SANS}" '
            f'{extra}>{escape(value)}</text>')


def rect(x, y, w, h, fill, radius=0, stroke=None, extra=''):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
            f'rx="{radius}" fill="{fill}" '
            + (f'stroke="{stroke}" ' if stroke else '') + f'{extra}/>')


def path(d, color=WHITE, sw=1.6, extra=''):
    return (f'<path d="{d}" fill="none" stroke="{color}" '
            f'stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round" {extra}/>')


def circle(x, y, r, fill, stroke=None, extra=''):
    return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" '
            + (f'stroke="{stroke}" ' if stroke else '') + f'{extra}/>')


def svg(width, height, title, body, desc=None):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
            'aria-labelledby="title desc">'
            f'<title id="title">{escape(title)}</title>'
            f'<desc id="desc">{escape(desc or title)}</desc>'
            + ''.join(body) + '</svg>\n')


def icon(name, x, y, color, size=18):
    """Original line icons on a 20px grid; no third-party logo files."""
    paths = {
        'arrow': 'M 4 16 L 16 4 M 6 4 H 16 V 14',
        'globe': 'M 2 10 H 18 M 10 2 C 4 6 4 14 10 18 C 16 14 16 6 10 2',
        'mail': 'M 2 5 H 18 V 15 H 2 Z M 2 5 L 10 11 L 18 5',
        'link': 'M 8 6 L 11 3 Q 14 0 17 3 Q 20 6 17 9 L 14 12 M 12 14 L 9 17 Q 6 20 3 17 Q 0 14 3 11 L 6 8 M 7 13 L 13 7',
        'code': 'M 6 5 L 1 10 L 6 15 M 14 5 L 19 10 L 14 15 M 12 3 L 8 17',
        'grid': 'M 2 2 H 8 V 8 H 2 Z M 12 2 H 18 V 8 H 12 Z M 2 12 H 8 V 18 H 2 Z M 12 12 H 18 V 18 H 12 Z',
        'repo': 'M 4 2 H 17 V 18 H 4 Q 1 18 1 15 V 5 Q 1 2 4 2 M 1 14 H 17 M 6 5 H 12 M 6 8 H 10',
        'chart': 'M 2 2 V 18 H 19 M 6 14 V 10 M 11 14 V 6 M 16 14 V 3',
        'stack': 'M 1 6 L 10 1 L 19 6 L 10 11 Z M 1 10 L 10 15 L 19 10 M 1 14 L 10 19 L 19 14',
        'work': 'M 2 6 H 18 V 17 H 2 Z M 7 6 V 3 H 13 V 6 M 2 10 L 10 13 L 18 10 M 10 11 V 14',
        'shield': 'M 10 1 L 18 4 V 9 Q 18 16 10 19 Q 2 16 2 9 V 4 Z M 6 10 L 9 13 L 14 7',
        'cloud': 'M 6 16 H 15 Q 20 16 19 11 Q 19 7 15 7 Q 14 1 9 2 Q 4 2 4 8 Q 0 8 1 12 Q 1 16 6 16',
        'flow': 'M 3 2 V 8 H 16 V 17 M 3 8 V 17 M 12 5 L 16 8 L 12 11',
        'pin': 'M 10 19 Q 2 11 3 7 Q 3 1 10 1 Q 17 1 17 7 Q 18 11 10 19 M 7 7 A 3 3 0 1 0 13 7 A 3 3 0 1 0 7 7',
        'study': 'M 1 7 L 10 2 L 19 7 L 10 12 Z M 4 9 V 14 Q 10 19 16 14 V 9 M 19 7 V 15',
        'chat': 'M 2 3 H 18 V 14 H 9 L 4 18 V 14 H 2 Z M 6 7 H 14 M 6 10 H 11',
        'check': 'M 3 10 L 8 15 L 17 5',
    }
    result = path(paths.get(name, paths['code']), color, 1.6)
    if name == 'globe': result = circle(10,10,8,'none',color,extra='stroke-width="1.6"') + result
    if name == 'linkedin':
        result = (rect(2,7,3,11,color,1) + circle(3.5,3.5,1.8,color)
                  + path('M 9 18 V 8 M 9 12 Q 9 7 14 8 Q 18 8 18 12 V 18',color,2.6))
    return f'<g transform="translate({x} {y}) scale({size/20:g})">{result}</g>'


BUTTONS = [
    # slug, label, width, icon, accent, filled
    ('portfolio','Portfolio',145,'globe',CYAN,True),
    ('linkedin','LinkedIn',139,'linkedin','#82b5ff',False),
    ('email','Escríbeme',152,'mail',VIOLET,False),
    ('repositories','Repositorios',176,'repo',LIME,False),
    ('all-projects','Todos mis proyectos',222,'grid',CYAN,True),
    ('app-piti','Abrir Manchester Piti',230,'arrow',CYAN,True),
    ('code-piti','Ver código',151,'code',CYAN,False),
    ('app-fantasya','Abrir Fantasya',184,'arrow',LIME,True),
    ('code-fantasya','Ver código',151,'code',LIME,False),
    ('app-worldcup','Abrir simulador',192,'arrow',VIOLET,True),
    ('code-worldcup','Ver código',151,'code',VIOLET,False),
    ('nav-stats','Estadísticas',175,'chart',CYAN,False),
    ('nav-stack','Stack',116,'stack',LIME,False),
    ('nav-projects','Proyectos',153,'grid',VIOLET,False),
    ('nav-career','Trayectoria',164,'work','#82b5ff',False),
    ('credential-security','Cloud Security',254,'shield',CYAN,False),
    ('credential-btp','SAP BTP',230,'cloud',LIME,False),
    ('credential-gateway','Integration Suite',270,'flow',VIOLET,False),
]


def button(item):
    slug,label,width,symbol,accent,filled=item
    credential=slug.startswith('credential-')
    height=44 if credential else 40
    fill=accent if filled else PANEL
    fg=NAVY if filled else WHITE
    edge=accent if filled else '#34465d'
    p=[rect(.5,.5,width-1,height-1,fill,10,edge)]
    if not filled:
        p += [rect(1,11,2,height-22,accent,1),
              path(f'M 13 1 H {width-13}',accent,.8,extra='opacity="0.32"')]
    else:
        p += [path(f'M 12 2 H {width-12}',WHITE,.9,extra='opacity="0.4"')]
    p += [icon(symbol,14,(height-18)/2,fg if filled else accent,18),
          text(43,height/2+4.5,label,13.5,fg,650)]
    if credential:
        p += [circle(width-20,height/2,8,'none',accent,extra='stroke-width="1.1"'),
              icon('check',width-25,height/2-5,accent,10)]
    save(slug+'.svg',svg(width,height,label,p))


TECHS = [
    ('btp','SAP BTP','SAP','#0070f2'),
    ('cpi','Cloud Integration','CPI','#008fd3'),
    ('groovy','Groovy','G','#4298b8'),
    ('cap','SAP CAP','CAP','#0070f2'),
    ('pipo','SAP PI/PO','PI','#0f7dc2'),
    ('cloudconnector','Cloud Connector','CC','#1976d2'),
    ('typescript','TypeScript','TS','#3178c6'),
    ('javascript','JavaScript','JS','#f7df1e'),
    ('react','React','atom','#61dafb'),
    ('nextjs','Next.js','N','#ededed'),
    ('angular','Angular','A','#e84272'),
    ('tailwind','Tailwind CSS','wave','#38bdf8'),
    ('nodejs','Node.js','N','#72bc54'),
    ('java','Java','J','#ee9a49'),
    ('spring','Spring Boot','S','#6db33f'),
    ('firebase','Firebase','flame','#ffca28'),
    ('mysql','MySQL','SQL','#65a8cb'),
    ('mongodb','MongoDB','leaf','#4db33d'),
    ('docker','Docker','D','#2496ed'),
    ('git','Git','branch','#f05032'),
    ('github','GitHub','GH','#f1f5fb'),
    ('postman','Postman','P','#ff6c37'),
    ('odata','OData V2 / V4','OD','#55d9ed'),
    ('rest','REST','API','#c6f568'),
    ('soap','SOAP','S','#b9a5ff'),
    ('hl7','HL7','H7','#f89a9f'),
    ('xml','XML','<>','#e8a75c'),
    ('json','JSON','{}','#dbc66e'),
]


def tech_symbol(symbol, x, y, color):
    p=[]
    if symbol=='atom':
        p += [f'<ellipse cx="{x+11}" cy="{y+10}" rx="10" ry="3.7" fill="none" stroke="{color}" stroke-width="1.1" transform="rotate({a} {x+11} {y+10})"/>' for a in [0,60,120]]
        p += [circle(x+11,y+10,1.8,color)]
    elif symbol=='wave':
        p += [f'<path d="M {x+1} {y+10} Q {x+6} {y+2} {x+11} {y+7} Q {x+16} {y+12} {x+22} {y+5} Q {x+18} {y+15} {x+12} {y+10} Q {x+6} {y+5} {x+1} {y+10}" fill="{color}"/>',
              f'<path d="M {x+1} {y+16} Q {x+6} {y+8} {x+11} {y+13} Q {x+16} {y+18} {x+22} {y+11} Q {x+18} {y+21} {x+12} {y+16} Q {x+6} {y+11} {x+1} {y+16}" fill="{color}"/>']
    elif symbol=='flame':
        p += [f'<path d="M {x+4} {y+18} L {x+5} {y+1} L {x+10} {y+9} L {x+14} {y+3} L {x+19} {y+17} L {x+11} {y+21} Z" fill="{color}"/>']
    elif symbol=='leaf':
        p += [f'<path d="M {x+11} {y+1} C {x+22} {y+10} {x+17} {y+18} {x+11} {y+20} C {x+3} {y+17} {x+1} {y+9} {x+11} {y+1}" fill="{color}"/>',path(f'M {x+11} {y+8} V {y+22}',NAVY,1.1)]
    elif symbol=='branch':
        p += [path(f'M {x+6} {y+4} V {y+17} M {x+6} {y+12} H {x+15} V {y+5}',color,1.6)]
        p += [circle(x+a,y+b,2,PANEL,color,extra='stroke-width="1.6"') for a,b in [(6,3),(6,18),(15,4)]]
    else:
        channels=[int(color[i:i+2],16)/255 for i in (1,3,5)]
        linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in channels]
        luminance=sum(v*k for v,k in zip(linear,[.2126,.7152,.0722]))
        chip_text=WHITE if luminance<.18 else NAVY
        p += [rect(x+1,y+2,21,19,color,4),text(x+11.5,y+15,symbol,9 if len(symbol)>2 else 11,chip_text,750,'text-anchor="middle"',mono=True)]
    return ''.join(p)


def tech(item):
    slug,label,symbol,color=item
    width=ceil(48+len(label)*6.9)
    p=[rect(.5,.5,width-1,29,PANEL,7,'#2b3b51'),
       tech_symbol(symbol,7,4,color),
       text(38,19.3,label,12.2,WHITE,550)]
    save('tech-'+slug+'.svg',svg(width,30,label,p))


STATUSES = [
    ('alsea','BTP & Integraciones · Alsea',268,'work',LIME),
    ('madrid','Madrid, ES',142,'pin',CYAN),
    ('unir','UNIR · En curso',176,'study',VIOLET),
    ('es','Español · Nativo',180,'chat','#f0b870'),
    ('en','English · B2',151,'chat','#82b5ff'),
]


def status(item):
    slug,label,width,symbol,accent=item
    p=[rect(.5,.5,width-1,31,PANEL,16,'#30425b'),
       icon(symbol,11,8,accent,16),
       text(36,20.5,label,12.5,WHITE,550)]
    save('status-'+slug+'.svg',svg(width,32,label,p))


THEMES={
    'dark':dict(bg=NAVY,panel=PANEL,text=WHITE,muted=SLATE,line='#283b54',cyan=CYAN,lime=LIME,violet=VIOLET,blue='#82b5ff',current='#13251d'),
    'light':dict(bg='#f2f6fb',panel='#ffffff',text='#102034',muted='#4e657e',line='#c5d5e6',cyan='#087c91',lime='#527600',violet='#7251c5',blue='#155eaa',current='#eff7dd'),
}
JOBS = [
    ('Inetum','2023–2025','SAP CPI · PI/PO','blue'),
    ('Timestamp','2025','RR. HH. · SuccessFactors','violet'),
    ('Sapas','2025–2026','SAP CAP · HL7','cyan'),
    ('Alsea','2026–actualidad','Responsable BTP & Integraciones','lime'),
]


def career(theme, mobile=False):
    t=THEMES[theme]
    w,h=(640,500) if mobile else (1200,220)
    p=[rect(.5,.5,w-1,h-1,t['bg'],20,t['line'])]
    p += [text(30,38,'Mi recorrido.',24,t['text'],650),
          text(w-30,36,'SAP · CLOUD · SOFTWARE',10 if mobile else 11,t['muted'],500,'text-anchor="end" letter-spacing="1.2"',mono=True)]
    if mobile:
        p += [path('M 61 117 V 429',t['line'],2)]
        for i,(name,dates,role,key) in enumerate(JOBS):
            accent=t[key]; y=70+104*i
            p += [rect(94,y,516,94,t['current'] if i==3 else t['panel'],13,accent if i==3 else t['line']),
                  circle(61,y+47,13,t['bg'],accent,extra='stroke-width="1.5"'),circle(61,y+47,4,accent),
                  path(f'M 74 {y+47} H 94',t['line'],1.2),
                  text(114,y+35,name,28,t['text'],650),
                  text(590,y+33,dates,15,accent,550,'text-anchor="end"',mono=True),
                  text(114,y+68,role,17,t['muted'],500)]
    else:
        p += [path('M 165 77 H 1035',t['line'],2)]
        for i,(name,dates,role,key) in enumerate(JOBS):
            accent=t[key]; x=30+i*290
            p += [path(f'M {x+135} 77 V 101',t['line'],1.3),circle(x+135,77,6,accent),
                  rect(x,101,270,95,t['current'] if i==3 else t['panel'],12,accent if i==3 else t['line']),
                  text(x+18,124,dates,12,accent,550,mono=True),
                  text(x+18,156,name,26,t['text'],650),
                  text(x+18,180,role,12.5,t['muted'],500)]
    save(f'career-{"mobile-" if mobile else ""}{theme}.svg',
         svg(w,h,'Trayectoria profesional de Adrián Tomás Cerdá',p,
             'Inetum, 2023–2025. Timestamp, 2025. Sapas, 2025–2026. Alsea, 2026–actualidad.'))


def save(name, content):
    ET.fromstring(content)
    (OUT/name).write_text(content,encoding='utf-8')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for item in BUTTONS: button(item)
    for item in TECHS: tech(item)
    for item in STATUSES: status(item)
    for theme in THEMES:
        career(theme)
        career(theme,True)
    files=sorted(OUT.glob('*.svg'))
    for file in files:
        root=ET.parse(file).getroot()
        assert root.attrib.get('role')=='img', file
        for element in root.iter():
            assert element.tag.rsplit('}',1)[-1] not in {'script','foreignObject','image','a'}, file
            assert not any(key.rsplit('}',1)[-1]=='href' for key in element.attrib), file
        print(f'{file.name}: {root.attrib["width"]}×{root.attrib["height"]}')
    print(f'{len(files)} SVG assets; {sum(f.stat().st_size for f in files):,} bytes')


if __name__=='__main__':
    main()
