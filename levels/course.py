"""A track laid out as a sequence of segments, sampled along its centre line.

The course starts at the origin heading +X (spline point 0: the start line and grid, SW_RACER_RE
swrObjJdge_GetSpawnTransform 0x465840) and turns left (counter-clockwise). Each segment knows its
length, how its height and bank change along it, its road width, whether it has road under it
(a gap for jumps) and the station it belongs to. Distances, heights and widths are game units.
"""
import math

from mathutils import Vector

import lib

STEP = 100.0   # centre-line sample spacing


class Segment:
    def __init__(self, length, station, rise=None, turn=0.0, radius=0.0, bank=None, width=600.0,
                 solid=True, drop=0.0):
        self.length = length
        self.station = station
        self.rise = rise or (lambda u: 0.0)    # height change since the segment start, u in [0, length]
        self.turn = turn                        # radians, + = left
        self.bank = bank or (lambda u: 0.0)     # roll in degrees, + = road's right edge up (leans into a left turn)
        self.width = width
        self.solid = solid
        self.drop = drop                        # height step at the segment start (a cliff)


def straight(length, station, **kwargs):
    return Segment(length, station, **kwargs)


def ramp(length, degrees, station, **kwargs):
    slope = math.tan(math.radians(degrees))
    return Segment(length, station, rise=lambda u: u * slope, **kwargs)


def arc(radius, degrees, station, bank=0.0, ease=0.25, **kwargs):
    """A turn, left for positive degrees. bank eases in over the first and out over the last
    `ease` of the arc."""
    length = radius * math.radians(abs(degrees))

    def roll(u):
        t = u / length
        k = min(1.0, t / ease, (1 - t) / ease) if ease > 0 else 1.0
        return bank * max(0.0, k)
    return Segment(length, station, turn=math.radians(degrees), radius=radius, bank=roll, **kwargs)


class Course:
    def __init__(self, segments, origin=(0.0, 0.0)):
        """origin: where the start line is. Collision and visual vertices are int16 game units
        (SW_RACER_RE src/types.h swrModel_Mesh), so a course must stay within +-32767."""
        self.segments = segments
        self.origin = Vector(origin)
        self.samples = []   # dicts: s, pos (Vector), heading, bank, width, solid, station, seg
        s, pos, heading, z = 0.0, Vector(origin), 0.0, 0.0
        for index, seg in enumerate(segments):
            z -= seg.drop
            n = max(1, int(math.ceil(seg.length / STEP)))
            z0, h0, p0 = z, heading, pos.copy()
            for i in range(n + 1):
                u = seg.length * i / n
                if seg.turn:
                    a = h0 + seg.turn * u / seg.length
                    r = seg.length / seg.turn
                    p = p0 + r * Vector((math.sin(a) - math.sin(h0), -math.cos(a) + math.cos(h0)))
                else:
                    a = h0
                    p = p0 + u * Vector((math.cos(h0), math.sin(h0)))
                self.samples.append(dict(s=s + u, pos=Vector((p.x, p.y, z0 + seg.rise(u))), heading=a,
                                         bank=seg.bank(u), width=seg.width, solid=seg.solid,
                                         station=seg.station, seg=index, first=(i == 0)))
            s += seg.length
            heading = h0 + seg.turn
            pos = p
            z = z0 + seg.rise(seg.length)
        self.length = s
        self.end = (pos, heading, z)

    def closure_error(self):
        pos, heading, z = self.end
        return (pos - self.origin).length, math.degrees((heading + math.pi) % (2 * math.pi) - math.pi), z

    def edges(self, sample):
        h, roll = sample['heading'], math.radians(sample['bank'])
        side = Vector((-math.sin(h), math.cos(h), 0.0))      # to the left
        half = sample['width'] / 2
        lift = Vector((0, 0, half * math.sin(roll)))
        across = side * half * math.cos(roll)
        p = sample['pos']
        # a left-leaning bank (positive) raises the right edge
        return p + across - lift, p - across + lift

    # MARK: geometry

    def road(self, collection, mat, name="road", colors=None, max_quads=900):
        """Road meshes: one per run of solid samples in the same segment (split to stay under the
        add-on's 2048-triangle limit). Returns {station: [objects]}."""
        objects = {}
        runs, current = [], []
        for a, b in zip(self.samples, self.samples[1:]):
            if b['first']:          # segment boundary: a and b are the same place (or a cliff)
                if current:
                    runs.append(current)
                current = []
                continue
            if not self.segments[b['seg']].solid:
                if current:
                    runs.append(current)
                current = []
                continue
            current.append((a, b))
            if len(current) >= max_quads:
                runs.append(current)
                current = []
        if current:
            runs.append(current)
        for i, run in enumerate(runs):
            verts, faces, uvs, cols = [], [], [], []
            station = run[0][1]['station']
            for a, b in run:
                la, ra = self.edges(a)
                lb, rb = self.edges(b)
                base = len(verts)
                verts.extend([tuple(ra), tuple(rb), tuple(lb), tuple(la)])
                faces.append((base, base + 1, base + 2, base + 3))
                v0 = a['s'] / a['width']
                shift = math.floor(v0)
                v1 = b['s'] / a['width']
                uvs.extend([(0, v0 - shift), (0, v1 - shift), (1, v1 - shift), (1, v0 - shift)])
                if colors:
                    c = colors.get(station, (1, 1, 1))
                    cols.extend([c] * 4)
            obj = lib.mesh_object(f"{name}_{i:03d}_{station}", verts, faces, uvs, collection, mat,
                                  colors=cols if colors else None)
            lib.set_surface(obj)
            objects.setdefault(station, []).append(obj)
        return objects

    def frame(self, s):
        """The sample nearest distance s along the course."""
        return min(self.samples, key=lambda smp: abs(smp['s'] - s))

    def station_range(self, station):
        ss = [smp['s'] for smp in self.samples if smp['station'] == station]
        return min(ss), max(ss)

    def extent(self):
        xs = [abs(c) for smp in self.samples for c in smp['pos']]
        return max(xs)

    def spline_points(self, spacing=500.0):
        points, next_s = [], 0.0
        for smp in self.samples:
            if smp['s'] >= next_s - 1e-6 and smp['s'] < self.length - spacing / 2:
                points.append(tuple(smp['pos']))
                next_s = smp['s'] + spacing
        return points

    def describe(self):
        """The centre line every STEP for expectations.json: [s, x, y, z, station]."""
        return [[round(smp['s'], 1), round(smp['pos'].x, 1), round(smp['pos'].y, 1),
                 round(smp['pos'].z, 1), smp['station']] for smp in self.samples]


def exhibit_loop(exhibits, gap=300.0, tail=(), radius=2500.0, close=2000.0):
    """A stadium loop with the exhibits [(name, length)] in a row along both straights, plain road
    ("between") after each, then the tail segments, and a closing straight ("grid") before the line.
    Centred on the origin (vertices are int16)."""
    bottom, top = [straight(1000, "start")], []
    half = sum(length + gap for _, length in exhibits) / 2
    side = bottom
    for name, length in exhibits:
        side.append(straight(length, name))
        side.append(straight(gap, "between"))
        if side is bottom and sum(seg.length for seg in bottom) > half:
            side = top
    top += list(tail)
    a = sum(seg.length for seg in bottom)
    used = sum(seg.length for seg in top)
    if used > a + close:
        bottom.append(straight(used - a - close, "between"))
        a = used - close
    top.append(straight(a + close - used, "between"))
    segs = bottom + [arc(radius, 180, "turn")] + top + [arc(radius, 180, "turn_home"), straight(close, "grid")]
    course = Course(segs, origin=(-(a - close) / 2, -radius))
    assert course.extent() < 32000, f"course reaches {course.extent():.0f}, past the int16 vertex range"
    dist, heading_err, z_err = course.closure_error()
    assert dist < 1 and abs(heading_err) < 0.01 and abs(z_err) < 1, course.closure_error()
    return course
