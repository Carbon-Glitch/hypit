"""Author a deterministic HyperFrames calligraphic contour/fill title layer.

Uses the supplied local font only while authoring paths; does not copy the font.
No generation service, network submission, footage editing or quality verdict.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen


def build(text: str, font_path: Path, output: Path, width: int, height: int,
          duration: float, background: str, shadow: str, metal: str,
          highlight: str, glint: str, overlay: bool, gsap: str) -> Path:
    if not text.strip() or len(text) > 20:
        raise ValueError("Supply a readable short title; longer text needs a separate layout.")
    if width < 320 or height < 240 or duration < 4:
        raise ValueError("Canvas or duration does not support this title layout.")
    font = TTFont(str(font_path))
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    names = []
    for char in text:
        if ord(char) not in cmap:
            raise ValueError(f"Font lacks a title glyph: U+{ord(char):04X}")
        names.append(cmap[ord(char)])
    units = font['head'].unitsPerEm
    tracking = units * .075
    advances = [font['hmtx'][name][0] for name in names]
    extent = sum(advances) + tracking * (len(names) - 1)
    scale = min(width * .71 / extent, height * .31 / units)
    start = (width - extent * scale) / 2
    baseline = height * .58
    groups, mask_paths = [], []
    cursor = start
    for i, (name, advance) in enumerate(zip(names, advances)):
        pen = SVGPathPen(glyphs)
        glyphs[name].draw(pen)
        path = pen.getCommands()
        transform = f'translate({cursor:.3f},{baseline:.3f}) scale({scale:.6f},-{scale:.6f})'
        groups.append(f'''<g class="letter" transform="{transform}">
          <g id="fill-{i}" class="fill"><path d="{path}" fill="url(#metal)" filter="url(#texture)"/></g>
          <path id="outline-{i}" class="outline" d="{path}" fill="none" stroke="{highlight}"
            stroke-width="{units*.004:.2f}" stroke-linejoin="round"/>
        </g>''')
        mask_paths.append(f'<path transform="{transform}" d="{path}" fill="white"/>')
        cursor += (advance + tracking) * scale
    font.close()
    safe_title = html.escape(text)
    root_background = 'transparent' if overlay else background
    backdrop = '' if overlay else f'''<rect width="100%" height="100%" fill="{background}"/>
      <ellipse cx="{width*.52}" cy="{height*.65}" rx="{width*.35}" ry="{height*.10}"
        fill="{shadow}" opacity=".68" filter="url(#atmosphere)"/>
      <path d="M {width*.13} {height*.67} Q {width*.5} {height*.65} {width*.87} {height*.68}"
        fill="none" stroke="{shadow}" stroke-width="2" opacity=".55"/>'''
    factor = duration / 6
    animation = []
    for i in range(len(names)):
        delay = min(.14, .65 / max(1, len(names)-1)) * i
        animation.append(f'''{{const el=document.getElementById('outline-{i}');
          const length=el.getTotalLength(); el.style.strokeDasharray=length;
          tl.fromTo(el,{{strokeDashoffset:length,opacity:0}},
            {{strokeDashoffset:0,opacity:.88,duration:{1.48*factor},ease:'power2.inOut'}},{(.42+delay)*factor});}}
          tl.fromTo('#fill-{i}',{{opacity:0,y:9,filter:'blur(10px)'}},
            {{opacity:1,y:0,filter:'blur(0px)',duration:{1.45*factor},ease:'power3.out'}},{(1.1+delay)*factor});''')
    page = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width={width}, height={height}"/>
<title>{safe_title} · authored title reveal</title><script src="{html.escape(gsap, quote=True)}"></script>
<style>*{{box-sizing:border-box}}html,body{{margin:0;width:{width}px;height:{height}px;overflow:hidden;background:{root_background}}}
#main{{width:100%;height:100%}}.scene-content{{width:100%;height:100%;padding:0;display:flex;align-items:center;justify-content:center}}
svg{{width:100%;height:100%;overflow:visible}}.fill,.outline{{will-change:opacity,transform}}#sweep{{mix-blend-mode:screen}}
</style></head><body>
<div id="main" data-composition-id="main" data-start="0" data-duration="{duration}"
 data-width="{width}" data-height="{height}">
 <div id="title-layer" class="clip scene-content" data-start="0" data-duration="{duration}" data-track-index="0">
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="{safe_title}">
   <defs>
    <linearGradient id="metal" x1="0" y1="0" x2=".9" y2="1" gradientUnits="objectBoundingBox">
     <stop offset="0" stop-color="{metal}"/><stop offset=".28" stop-color="{highlight}"/>
     <stop offset=".53" stop-color="{metal}"/><stop offset=".79" stop-color="{highlight}"/><stop offset="1" stop-color="{metal}"/>
    </linearGradient>
    <linearGradient id="light"><stop stop-color="{glint}" stop-opacity="0"/>
     <stop offset=".48" stop-color="{glint}" stop-opacity=".95"/><stop offset="1" stop-color="{glint}" stop-opacity="0"/></linearGradient>
    <filter id="texture" x="-10%" y="-10%" width="120%" height="120%">
     <feTurbulence type="fractalNoise" baseFrequency=".024" numOctaves="2" seed="7" result="noise"/>
     <feColorMatrix in="noise" type="saturate" values="0"/>
     <feComposite in2="SourceAlpha" operator="in"/>
     <feBlend in="SourceGraphic" mode="soft-light"/>
    </filter>
    <filter id="atmosphere"><feGaussianBlur stdDeviation="{height*.055}"/></filter>
    <filter id="bloom"><feGaussianBlur stdDeviation="4"/></filter>
    <mask id="title-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="{width}" height="{height}">{''.join(mask_paths)}</mask>
   </defs>
   {backdrop}
   <g id="artwork">{''.join(groups)}
    <g mask="url(#title-mask)"><g id="sweep" opacity="0">
      <rect x="{-width*.23}" y="0" width="{width*.15}" height="{height}" fill="url(#light)"/>
      <rect x="{-width*.23}" y="0" width="{width*.15}" height="{height}" fill="url(#light)" filter="url(#bloom)"/>
    </g></g>
   </g>
  </svg>
 </div>
</div>
<script>window.__timelines=window.__timelines||{{}};const tl=gsap.timeline({{paused:true}});
{''.join(animation)}
tl.fromTo('#sweep',{{x:0,opacity:0}},{{x:{width*1.65},opacity:.8,duration:{1.14*factor},ease:'sine.inOut'}},{2.6*factor});
tl.to('#sweep',{{opacity:0,duration:{.35*factor},ease:'sine.out'}},{3.78*factor});
tl.to('#artwork',{{opacity:0,y:-8,duration:{.84*factor},ease:'power2.in'}},{5.15*factor});
window.__timelines.main=tl;
</script></body></html>'''
    output.mkdir(parents=True, exist_ok=True)
    path = output / 'index.html'
    path.write_text(page, encoding='utf-8')
    (output / 'title-reveal-config.json').write_text(json.dumps({
        'text': text, 'font_source': str(font_path), 'width': width, 'height': height,
        'duration': duration, 'overlay': overlay,
        'status': 'mechanism_proof_not_design_acceptance',
        'colors': {'background': background, 'shadow': shadow, 'metal': metal,
                   'highlight': highlight, 'glint': glint},
        'mechanism': 'glyph contour -> textured fill -> light sweep -> readable hold -> departure',
        'boundary': 'Contour reveal, not handwriting stroke order; actual footage integration requires review.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--text', required=True)
    p.add_argument('--font', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--width', type=int, default=1920)
    p.add_argument('--height', type=int, default=1080)
    p.add_argument('--duration', type=float, default=6)
    p.add_argument('--background', default='#07171D')
    p.add_argument('--shadow', default='#183A42')
    p.add_argument('--metal', default='#AD7842')
    p.add_argument('--highlight', default='#F3E0B9')
    p.add_argument('--glint', default='#FFF4D8')
    p.add_argument('--overlay', action='store_true')
    p.add_argument('--gsap', default='./gsap.min.js', help='Pinned local GSAP script or verified static asset URL')
    a = p.parse_args()
    try:
        result = build(a.text, a.font, a.out, a.width, a.height, a.duration,
                       a.background, a.shadow, a.metal, a.highlight, a.glint, a.overlay, a.gsap)
    except (OSError, ValueError) as exc:
        print('TITLE_AUTHORING_FAILED: ' + str(exc))
        return 1
    print('TITLE_SOURCE_AUTHORED: ' + str(result.resolve()))
    print('Run HyperFrames check/snapshot/render and inspect actual output; no media was rendered here.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
