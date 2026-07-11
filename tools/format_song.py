#!/usr/bin/env python3
"""Format a raw chord chart into Music Markdown (c1:/l1:) layout.

Takes a plain chord-over-lyrics chart (the shape you get pasting from a
tab site) and emits the `# Title` / `## Section` / `c1:` / `l1:` format
used by this library. Because the `c1: ` and `l1: ` prefixes are both
exactly four characters, the column positions of chords over lyrics are
preserved byte-for-byte from the input.

Usage:
    tools/format_song.py "Artist - Song.md"            # print to stdout
    tools/format_song.py "Artist - Song.md" -i         # rewrite in place
    tools/format_song.py "Artist - Song.md" -o out.md  # write to out.md
    tools/format_song.py --self-test                   # run built-in checks

Input shape expected:
    Line 1            -> the title (becomes "# <title>")
    [Section]         -> section header (becomes "## Section")
    (Section)         -> also a section header
    chord line        -> a line of chords/positions; if the next line is
                         lyrics it is paired as c1:/l1:, otherwise emitted
                         as a standalone progression (Intro/Solo/etc.)
    lyric line        -> paired with the chord line above it, or emitted
                         with an empty c1: when the chord is held
    Capo/Key/etc.     -> non-chord lines before the first section or chord
                         are preserved verbatim as a preamble

Safety: the input is read fully into memory before anything is written,
and writing refuses to target the input path unless --in-place is given.
This tool exists because an earlier shell one-liner (`script in.md > in.md`)
truncated its own input before reading it.
"""
import argparse
import os
import re
import sys

# A chord token: root + optional accidental + optional quality/extension
# cluster + optional slash bass. Matches G, G7, Gm, Gmaj7, Gsus4, Cadd9,
# Am7, A6, D/F#, C#, Bb, Em, F#m7b5-ish shapes.
_CHORD = re.compile(
    r'^[A-G][#b]?'                       # root
    r'(?:m|maj|min|dim|aug|sus|add|M|\+|-|°|ø)*'  # quality words/symbols
    r'[0-9]*'                            # extension number
    r'(?:(?:sus|add|b|#)[0-9]+)*'        # trailing alterations e.g. add9, b5
    r'(?:/[A-G][#b]?)?$'                 # optional slash bass
)

# Tokens allowed to appear on a chord/progression line alongside chords.
# The renderer only accepts repeat counts in parenthesized form, e.g.
# `(x4)`; a bare `x4` is an invalid token. Bare forms are still accepted
# on *input* and normalized on output (see _normalize_repeats). A lone
# stop glyph like `X` is NOT a valid chord token, so it is deliberately
# excluded here — such a line falls through to plain-text handling.
_MARKER = re.compile(r'^(?:x[0-9]+|\(x[0-9]+\)|\|+)$', re.IGNORECASE)

# A bare repeat count as a standalone token, for normalization to (xN).
_BARE_REPEAT = re.compile(r'(?<!\()\bx([0-9]+)\b(?!\))', re.IGNORECASE)

_HEADER_BRACKET = re.compile(r'^\[(.+)\]$')
_HEADER_PAREN = re.compile(r'^\((.+)\)$')


def _is_chord_token(tok):
    return bool(_CHORD.match(tok) or _MARKER.match(tok))


def _normalize_repeats(line):
    """Rewrite bare repeat counts (x4) so the renderer accepts them."""
    return _BARE_REPEAT.sub(lambda m: '(x' + m.group(1) + ')', line)


def is_chord_line(line):
    """True if every whitespace-separated token is a chord or marker."""
    toks = line.split()
    if not toks:
        return False
    return all(_is_chord_token(t) for t in toks)


def is_header(stripped):
    m = _HEADER_BRACKET.match(stripped) or _HEADER_PAREN.match(stripped)
    return m.group(1).strip() if m else None


def format_chart(text):
    """Transform a raw chart string into Music Markdown. Pure; no I/O."""
    lines = [ln.rstrip('\n') for ln in text.split('\n')]
    while lines and lines[-1].strip() == '':
        lines.pop()
    if not lines:
        raise ValueError('empty input: expected at least a title line')

    out = ['# ' + lines[0].strip(), '']
    seen_body = False  # have we emitted a header or any chord/lyric yet?
    i = 1
    n = len(lines)

    def emit_header(name):
        nonlocal seen_body
        out.append('')
        out.append('## ' + name)
        out.append('')
        seen_body = True

    while i < n:
        line = lines[i]
        stripped = line.strip()
        if stripped == '':
            i += 1
            continue

        name = is_header(stripped)
        if name is not None:
            emit_header(name)
            i += 1
            continue

        if is_chord_line(line):
            # A leading standalone progression with no header yet is the Intro.
            if not seen_body:
                emit_header('Intro')
            # Look at the next non-empty line to decide pairing.
            nxt = lines[i + 1] if i + 1 < n else None
            nxt_stripped = nxt.strip() if nxt is not None else ''
            nxt_is_lyric = (
                nxt is not None
                and nxt_stripped != ''
                and is_header(nxt_stripped) is None
                and not is_chord_line(nxt)
            )
            if nxt_is_lyric:
                out.append('c1: ' + line)
                out.append('l1: ' + nxt)
                out.append('')
                i += 2
            else:
                out.append('c1: ' + _normalize_repeats(line))
                out.append('')
                seen_body = True
                i += 1
            continue

        # Non-chord line. Before any body content it's a preamble
        # annotation (Capo II, Key: G, ...) — keep it verbatim.
        if not seen_body:
            out.append(line)
            out.append('')
            i += 1
            continue

        # Otherwise it's a lyric line whose chord is held from above.
        # The renderer wants a lone `l1:` here — a bare empty `c1:` line
        # breaks voice pairing and prints the prefixes as literal text.
        out.append('l1: ' + line)
        out.append('')
        i += 1

    # Collapse runs of blank lines to a single blank.
    collapsed = []
    for ln in out:
        if ln == '' and collapsed and collapsed[-1] == '':
            continue
        collapsed.append(ln)
    return '\n'.join(collapsed).strip('\n') + '\n'


def _write(text, dst):
    """Write atomically: temp file in the same dir, then os.replace."""
    d = os.path.dirname(os.path.abspath(dst)) or '.'
    tmp = os.path.join(d, '.' + os.path.basename(dst) + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(text)
    os.replace(tmp, dst)


def _self_test():
    raw = (
        "Artist - Test Song\n"
        "\n"
        "D    A    C    G\n"
        "\n"
        "[Verse 1]\n"
        "   D\n"
        "First line of the verse\n"
        " \n"
        "A held-chord line with no chord above\n"
        "\n"
        "[Chorus]\n"
        "        Em            C\n"
        "In your head, zombie\n"
        "\n"
        "[Instrumental]\n"
        "Em C G D/F# x4\n"
    )
    got = format_chart(raw)
    checks = [
        got.startswith('# Artist - Test Song\n'),
        '## Intro\n' in got,                         # leading progression labeled
        '\nc1: D    A    C    G\n' in got,           # progression preserved
        '## Verse 1\n' in got,
        'c1:    D\nl1: First line of the verse\n' in got,  # alignment kept
        '\nl1: A held-chord line with no chord above\n' in got,  # lone l1:
        '\nc1:\n' not in got,  # never emit a bare empty chord line
        'c1: Em C G D/F# (x4)\n' in got,  # bare repeat count normalized
        'x4' not in got.replace('(x4)', ''),  # no bare x4 survives
        'c1:         Em            C\nl1: In your head, zombie\n' in got,
        '\n\n\n' not in got,                          # no triple blanks
    ]
    # Chord grammar spot checks.
    grammar = [
        is_chord_line('D A C G'),
        is_chord_line('Em C G D/F#  x4'),
        is_chord_line('Cadd9 A6 Gmaj7 F#m'),
        not is_chord_line('In your head, zombie'),
        not is_chord_line('Am I the only one'),      # word-y line, not chords
        not is_chord_line('Be still my heart'),
    ]
    ok = all(checks) and all(grammar)
    for idx, c in enumerate(checks):
        print(f'  format check {idx}: {"ok" if c else "FAIL"}')
    for idx, c in enumerate(grammar):
        print(f'  grammar check {idx}: {"ok" if c else "FAIL"}')
    print('SELF-TEST:', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


def main(argv=None):
    p = argparse.ArgumentParser(description='Format a raw chord chart into Music Markdown.')
    p.add_argument('input', nargs='?', help='raw chart .md file')
    p.add_argument('-o', '--out', help='write formatted output to this path')
    p.add_argument('-i', '--in-place', action='store_true',
                   help='rewrite the input file in place')
    p.add_argument('--self-test', action='store_true', help='run built-in checks and exit')
    args = p.parse_args(argv)

    if args.self_test:
        return _self_test()
    if not args.input:
        p.error('input file required (or use --self-test)')

    with open(args.input, encoding='utf-8') as f:
        text = f.read()
    formatted = format_chart(text)

    dst = args.out or (args.input if args.in_place else None)
    if dst is None:
        sys.stdout.write(formatted)
        return 0

    same = os.path.realpath(dst) == os.path.realpath(args.input)
    if same and not args.in_place:
        p.error(f'refusing to overwrite input {args.input!r}; pass --in-place if intended')
    _write(formatted, dst)
    print(f'wrote {dst} ({len(formatted)} bytes)', file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
