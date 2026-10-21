"""In-world signs: text drawn with one 128x128 glyph atlas texture.

Only about 52 texture slots are free past the stock textureblock (the add-on stops at 1700), so
every sign shares this atlas. Each character is a quad UV-mapped onto its atlas cell; the atlas is
white glyphs on a dark ground and vertex colors tint it (the default combiner is TEXEL0 x SHADE).
"""
import bpy

import lib

CELL = 16          # atlas cell size in pixels; 8 x 8 cells
GRID = 8
# 5x7 glyphs, one string of 7 rows of 5 columns ('#' = lit) per character
FONT = {
    'A': " ### #   ##   #######   ##   ##   #", 'B': "#### #   ##### #   ##   ##   ##### ",
    'C': " ### #   ##    #    #    #   # ### ", 'D': "#### #   ##   ##   ##   ##   ##### ",
    'E': "######    ###  #    #    #    #####", 'F': "######    ###  #    #    #    #    ",
    'G': " ### #   ##    # ####   ##   # ####", 'H': "#   ##   #######   ##   ##   ##   #",
    'I': " ###   #    #    #    #    #   ### ", 'J': "  ###   #    #    # #  # #  #  ##  ",
    'K': "#   ##  # # #  ##   # #  #  # #   #", 'L': "#    #    #    #    #    #    #####",
    'M': "#   ### ### # ##   ##   ##   ##   #", 'N': "#   ###  ## # ##  ###   ##   ##   #",
    'O': " ### #   ##   ##   ##   ##   # ### ", 'P': "#### #   ##   ##### #    #    #    ",
    'Q': " ### #   ##   ##   ## # ##  #  ## #", 'R': "#### #   ##   ##### # #  #  # #   #",
    'S': " #####    #     ###     #    ##### ", 'T': "#####  #    #    #    #    #    #  ",
    'U': "#   ##   ##   ##   ##   ##   # ### ", 'V': "#   ##   ##   ##   ##   # # #   #  ",
    'W': "#   ##   ##   ## # ## # ## # # # # ", 'X': "#   ##   # # #   #   # # #   ##   #",
    'Y': "#   ##   # # #   #    #    #    #  ", 'Z': "#####    #   #   #   #   #    #####",
    '0': " ### #   ##  ### # ###  ##   # ### ", '1': "  #   ##    #    #    #    #   ### ",
    '2': " ### #   #    #   #   #   #   #####", '3': "#####   #   #     #     ##   # ### ",
    '4': "   #   ##  # # #  ######   #    #  ", '5': "######    ####     #    ##   # ### ",
    '6': "  ##  #   #    #### #   ##   # ### ", '7': "#####    #   #   #   #    #    #   ",
    '8': " ### #   ##   # ### #   ##   # ### ", '9': " ### #   ##   # ####    #   #  ##  ",
    '.': "                         ##   ##   ", ',': "                     ##    #   #   ",
    '-': "               #####               ", '+': "       #    #  #####  #    #       ",
    '/': "    #    #   #   #   #    #    #   ", ':': "      ##   ##        ##   ##       ",
    '%': "##   ##  #   #   #   #   #  ##   ##", '=': "          #####     #####          ",
    '(': "   #   #   #    #    #     #     # ", ')': " #     #     #    #    #   #   #   ",
    '<': "   #   #   #   #     #     #     # ", '>': " #     #     #     #   #   #   #   ",
    '#': " # #  # # ##### # # ##### # #  # # ", '?': " ### #   #    #   #   #         #  ",
    'x': "     #   # # #   #   # # #   #     ", "'": "  #    #   #                       ",
    '^': "  #   # # #   #                    ", '|': "  #    #    #    #    #    #    #  ",
    '_': "                              #####", '!': "  #    #    #    #    #         #  ",
    '*': "     # # #  #  #####  #  # # #     ", '~': "      #   # # #   #                ",
}
assert all(len(rows) == 35 for rows in FONT.values())
CHARS = [' '] + sorted(FONT)        # cell 0 is blank
assert len(CHARS) <= GRID * GRID
DEGREE = '^'                        # the atlas has no degree sign; ^ draws a small caret


def atlas_image(name="sign_atlas"):
    size = CELL * GRID
    ground, ink = (0.08, 0.08, 0.1, 1.0), (1.0, 1.0, 1.0, 1.0)
    pixels = [ground] * (size * size)
    for index, ch in enumerate(CHARS):
        rows = FONT.get(ch)
        if rows is None:
            continue
        cx, cy = (index % GRID) * CELL, (GRID - 1 - index // GRID) * CELL
        for r in range(7):
            for c in range(5):
                if rows[r * 5 + c] != '#':
                    continue
                # 2x scale, centred: 10x14 inside the 16x16 cell; image rows run bottom-up
                for dy in range(2):
                    for dx in range(2):
                        x = cx + 3 + c * 2 + dx
                        y = cy + CELL - 2 - (r * 2 + dy) - 1
                        pixels[y * size + x] = ink
    image = bpy.data.images.new(name, size, size, alpha=False)
    image.pixels = [v for p in pixels for v in p]
    image.pack()
    return image


def cell_uv(ch):
    index = CHARS.index(ch) if ch in CHARS else 0
    u0, v0 = (index % GRID) / GRID, (GRID - 1 - index // GRID) / GRID
    inset = 0.5 / (CELL * GRID)  # half a texel, so bilinear filtering doesn't bleed the next cell
    u1, v1 = u0 + 1 / GRID - inset, v0 + 1 / GRID - inset
    return [(u0 + inset, v0 + inset), (u1, v0 + inset), (u1, v1), (u0 + inset, v1)]


def sign(name, lines, origin, facing, collection, mat, char=60.0, color=(1.0, 0.85, 0.3),
         ground=(0.35, 0.35, 0.45), post=True):
    """A billboard of text lines standing at origin (game units, bottom centre), its face turned to
    the facing direction (x, y). Characters are char game units tall. Visual only (no collision)."""
    from mathutils import Vector
    lines = [line.upper() for line in lines]
    width = max(len(line) for line in lines) * char * 0.75 + char
    height = len(lines) * char * 1.15 + char * 0.5
    f = Vector((facing[0], facing[1], 0)).normalized()
    right = Vector((-f.y, f.x, 0))   # to the reader's right when they look along -f at the sign
    base = Vector(origin) + Vector((0, 0, 120 if post else 0))
    verts, faces, uvs, colors = [], [], [], []

    def add_quad(corners, uv, rgb):
        start = len(verts)
        verts.extend(tuple(c) for c in corners)
        faces.append((start, start + 1, start + 2, start + 3))
        uvs.extend(uv)
        colors.extend([rgb] * 4)

    blank = cell_uv(' ')
    up = Vector((0, 0, 1))
    # the board, set back a little from the glyphs
    back = -f * 2
    left_edge = base - right * (width / 2) + back
    add_quad([left_edge, left_edge + right * width, left_edge + right * width + up * height,
              left_edge + up * height], blank, ground)
    for row, line in enumerate(lines):
        y = height - char * 0.75 - row * char * 1.15
        x0 = -len(line) * char * 0.75 / 2
        for i, ch in enumerate(line):
            if ch == ' ':
                continue
            p = base + right * (x0 + i * char * 0.75) + up * (y - char / 2)
            add_quad([p, p + right * char * 0.75, p + right * char * 0.75 + up * char, p + up * char],
                     cell_uv(ch), color)
    if post:
        p = Vector(origin) - right * 10
        add_quad([p, p + right * 20, p + right * 20 + up * 120, p + up * 120], blank, ground)
    obj = lib.mesh_object(name, verts, faces, uvs, collection, mat, visible=True, collidable=False,
                          colors=colors)
    mat.use_backface_culling = False
    return obj
