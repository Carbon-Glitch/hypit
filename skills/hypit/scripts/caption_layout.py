"""Standalone caption layout from the local short-drama customization.
Packaged here so installing this skill does not require a sibling skill.
"""
import math
import re

PALETTES = {
    'cinema': {'font': 'Noto Sans CJK SC', 'size': .036, 'outline': .0018, 'bottom': .17,
               'color': '#F4F1EA', 'accent': '#E4C78E', 'bold': False, 'fade_ms': 0},
    'clear': {'font': 'Noto Sans CJK SC', 'size': .043, 'outline': .003, 'bottom': .21,
              'color': '#FFFFFF', 'accent': '#F0D37B', 'bold': True, 'fade_ms': 0},
    'editorial': {'font': 'Noto Sans CJK SC', 'size': .04, 'outline': .002, 'bottom': .19,
                  'color': '#F7F6F1', 'accent': '#C2D4CC', 'bold': True, 'fade_ms': 70},
}

def color(value):
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        raise ValueError('Subtitle colors use #RRGGBB')
    return '&H00' + value[5:7] + value[3:5] + value[1:3] + '&'

def numeric(value, low, high, label):
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{label} must be in {low}..{high}')
    return value

def escaped(text):
    return str(text).replace('\\', '＼').replace('{', '｛').replace('}', '｝').replace('\n', r'\N')

def clock(seconds):
    value = round(seconds * 100)
    return f'{value // 360000}:{value // 6000 % 60:02}:{value // 100 % 60:02}.{value % 100:02}'

def cue_ass(rows, width, height, config):
    """Keep each cue's exact window. Layout never manufactures speech timing."""
    name = config.get('preset', 'cinema')
    if name not in PALETTES:
        raise ValueError('Unknown subtitle preset: ' + str(name))
    theme = {**PALETTES[name], **config}
    font = theme['font']
    if any(c in font for c in ',\r\n'):
        raise ValueError('Invalid subtitle font family')
    size = height * numeric(theme['size'], .015, .12, 'font size fraction')
    outline = height * numeric(theme['outline'], 0, .015, 'outline fraction')
    bottom = height * numeric(theme['bottom'], .03, .45, 'bottom fraction')
    margin = max(12, width * .065)
    header = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,{font},{size:.2f},{color(theme['color'])},{color(theme['accent'])},&H00181818,&H80000000,{-1 if theme['bold'] else 0},0,0,0,100,100,0,0,1,{outline:.2f},0,2,{margin:.0f},{margin:.0f},{bottom:.0f},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    result = []
    for index, row in enumerate(rows):
        override = {**theme.get('cues', {}).get(str(index + 1), {}), **row.get('style', {})}
        text = row['text']
        tags = ''
        if 'x' in override or 'y' in override:
            x = numeric(override.get('x', .5), 0, 1, 'cue x') * width
            y = numeric(override.get('y', 1 - theme['bottom']), 0, 1, 'cue y') * height
            tags += f'{{\\an2\\pos({x:.1f},{y:.1f})}}'
        fade = numeric(override.get('fade_ms', theme['fade_ms']), 0, 500, 'cue fade')
        fade = min(fade, (row['end'] - row['start']) * 250)
        if fade:
            tags += f'{{\\fad({fade:.0f},{fade:.0f})}}'
        # Explicit line breaks or smart ASS wrapping share the SAME cue interval.
        words = sorted({w for w in row.get('keys', []) if w and w in text}, key=len, reverse=True)
        shown = ''
        cursor = 0
        for match in re.finditer('|'.join(re.escape(w) for w in words), text) if words else []:
            shown += escaped(text[cursor:match.start()])
            shown += '{\\c' + color(theme['accent']) + '}' + escaped(match.group()) + '{\\c' + color(theme['color']) + '}'
            cursor = match.end()
        shown += escaped(text[cursor:])
        result.append(f'Dialogue: 0,{clock(row["start"])},{clock(row["end"])},Main,,0,0,0,,{tags}{shown}')
    return header + '\n'.join(result) + '\n'
