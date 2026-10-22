"""Museum, surfaces wing: one lane per surface flag, each a collision mesh of its own.

Every exhibit checks two things:
- **Parity:** the bits the game reads from the mesh under the pod (telemetry `surf` / `spec`) are
  exactly the flags set on it in Blender.
- **Behaviour:** what swrRace_UpdateSurfaceTag (SW_RACER_RE src/Swr/swrRace.c:3318-3407) and the
  physics do with them.

The fall pad sits in a shallow pit (20 under the road) near the end. The game respawns a pod
on a Fall surface only once it is within 30 of it (not airborne); a pod falls slowly (about 230
units in the first 1.8 s off a lip), so a deeper pit is flown over before the pod gets that close.

Zone load/unload exhibits are left out: folder custom tracks run as planet 1 / sub-track 0, where
the game derives zones from the pod's position (swrObjJdge_InitTrack 0x466BD0).
"""
import math

from mathutils import Vector

import course as C
import lib
import signs

R = 2500.0
GAP = 300.0         # plain road between exhibits, so samples don't straddle two lanes
SRC = "SW_RACER_RE src/Swr/swrRace.c:3318-3407 (swrRace_UpdateSurfaceTag)"

# flag bits as the game names them (src/types_enums.h swrVehicleReaction, swrObjTest_FLAG0/1)
SURF = {"ZOn": 0x1, "ZOff": 0x2, "Fast": 0x4, "Slow": 0x8, "Swst": 0x10, "Slip": 0x20, "Dust": 0x40,
        "Snow": 0x80, "Wet": 0x100, "Ruff": 0x200, "Swmp": 0x400, "NSnw": 0x800, "Mirr": 0x1000,
        "Lava": 0x2000, "Fall": 0x4000, "Soft": 0x8000, "NRsp": 0x10000, "Flat": 0x20000,
        "Side": 0x20000000}
SPEC = {"skybox_hide": 0x2, "skybox_show": 0x4, "strict_spline": 0x8, "elevation": 0x10, "magnet": 0x20}
F0_ZON = 0x2000000
F1 = {"swamp": 0x1, "side": 0x20, "mirr": 0x40, "full_raycast": 0x80, "magnet": 0x400, "lava": 0x40000,
      "fall": 0x80000, "soft": 0x100000, "flat": 0x800000}


def exhibit(name, length, flags=(), special=(), lines=(), predict=None, source=SRC, title=None):
    return dict(name=name, length=length, flags=list(flags), special=list(special), lines=list(lines),
                predict=predict or {}, source=source, title=title or name.upper())


def surface_bits(flags):
    return sum(SURF[f] for f in flags)


def exhibits():
    ex = [
        exhibit("plain", 600, lines=["NO FLAGS"], predict={"surf": 0, "spec": 0}),
        exhibit("fast", 2400, ["Fast"], lines=["SPEED +200", "AT 25/S"],
                predict={"bonus_max": {"gt": 50}},
                source=SRC + ": Fast eases surfaceSpeedBonus toward +200 at 25/s"),
        exhibit("slow", 1200, ["Slow"], lines=["SPEED X0.75"],
                predict={"sfac_min": {"lt": 0.8, "gt": 0.7}},
                source=SRC + ": Slow eases surfaceSpeedFactor toward 0.75 at 0.5/s (below 15 off the ground)"),
        exhibit("slip", 1500, ["Slip"], lines=["GRIP X0.2"], predict={"grip_min": {"lt": 0.3}},
                source=SRC + ": Slip eases surfaceGripFactor toward 0.2 at 0.5/s"),
        exhibit("swst", 300, ["Swst"], lines=["SPEED X0.1", "NO BOOST"],
                predict={"sfac_min": {"lt": 0.95}},
                source=SRC + ": Swst eases surfaceSpeedFactor toward 0.1 and cancels boost"),
        exhibit("recover", 1500, lines=["PLAIN"], predict={"surf": 0}),
        exhibit("lava", 1500, ["Lava"], lines=["HEAT -20/S"],
                predict={"f1_seen": {"bits": F1["lava"]}, "heat_drop": {"gt": 20}},
                source="SW_RACER_RE src/Swr/swrRace.c:4337-4374: on Lava engine temperature drains 20/s"),
    ]
    for flag, bit_name, text in (("Dust", None, "DUST KICK"), ("Snow", None, "SNOW KICK"),
                                 ("Wet", None, "SPLASH"), ("Ruff", None, "RUMBLE"),
                                 ("Swmp", "swamp", "SWAMP"), ("NSnw", None, "NO WEATHER"),
                                 ("Soft", "soft", "SOFT"), ("NRsp", None, "NO RESPAWN?"),
                                 ("Flat", "flat", "AI ONLY"), ("Side", "side", "AI BANKS"),
                                 ("Mirr", None, "REFLECTION")):
        predict = {}
        if flag == "Flat":
            # ON_FLAT is only set for AI pods: the autopilot lends the AI bit only inside
            # swrRace_CalcTargetTurnRate, not while UpdateSurfaceTag runs
            predict["f1_seen"] = {"no_bits": F1["flat"]}
        elif bit_name:
            predict["f1_seen"] = {"bits": F1[bit_name]}
        ex.append(exhibit(flag.lower(), 600, [flag], lines=[text], predict=predict))
    for special, f1_bit, text in (("magnet", "magnet", "MAGNET"), ("elevation", "full_raycast", "FULL RAYCAST"),
                                  ("strict_spline", None, "STRICT SPLINE"), ("skybox_hide", None, "SKY OFF"),
                                  ("skybox_show", None, "SKY ON")):
        predict = {"spec": SPEC[special], "surf": 0}
        if f1_bit:
            predict["f1_seen"] = {"bits": F1[f1_bit]}
        ex.append(exhibit(special, 900, special=[special], lines=[text], predict=predict,
                          source=SRC + ": behavior unk1 0x2/0x4 sky, 0x10 FULL_RAYCAST, 0x20 MAGNET"))
    ex += [
        exhibit("zon", 1200, ["ZOn"], lines=["ZERO-G ON"], predict={"f0_seen": {"bits": F0_ZON}},
                source=SRC + ": ZOn sets FLAG0_ZON (spline-follow physics)"),
        exhibit("zoff", 1200, ["ZOff"], lines=["ZERO-G OFF"], predict={},
                source=SRC + ": ZOff (only while ZON) starts the ZOFF transition"),
        exhibit("after_zoff", 1500, lines=["PLAIN"], predict={"surf": 0}),
    ]
    return ex


def layout(ex):
    # the fall pit at the end: a gap over the Fall pad (added in build)
    tail = [C.straight(600, "fall_lip"), C.straight(900, "fall", solid=False), C.straight(1200, "fall_out")]
    return C.exhibit_line([(e["name"], e["length"]) for e in ex], GAP, tail, R)


def build(addon):
    model, track, sky = lib.new_track_scene(addon)
    road_mat = lib.material(addon, "museum_road", lib.checker_image("museum_checker"))
    sign_mat = lib.material(addon, "museum_signs", signs.atlas_image())
    ex = exhibits()
    course = layout(ex)

    flagged = {e["name"]: e for e in ex}
    colors = {name: ((1.0, 0.75, 0.45) if name in flagged and (flagged[name]["flags"] or flagged[name]["special"])
                     else (0.85, 0.85, 0.85)) for name in {smp['station'] for smp in course.samples}}
    roads = course.road(track, road_mat, colors=colors)
    for name, objs in roads.items():
        for obj in objs:
            e = flagged.get(name)
            if e:
                lib.set_surface(obj, *e["flags"], **{s: True for s in e["special"]})
            lib.shade(obj)

    # the Fall pad, its top 20 under the road. It stays inside the pit's ends: the game respawns
    # the pod at the far end, and where the pad ran on under the road the ground cached under the
    # spline there was the pad, so the pod respawned onto it over and over
    s0, s1 = course.station_range("fall")
    a, b = course.frame(s0), course.frame(s1)
    mid = (a['pos'] + b['pos']) / 2
    pad = lib.box("fall_pad", tuple(mid + Vector((0, 0, -40))), ((b['pos'] - a['pos']).length - 20, 1200, 40),
                  track, road_mat, colors=None)
    lib.set_surface(pad, "Fall")
    lib.shade(pad, tint=(1.0, 0.4, 0.4))
    ex.append(exhibit("fall", 900, ["Fall"], lines=["PIT: FALL PAD", "RESPAWN ON CONTACT"],
                      predict={"respawns": True},
                      source="SW_RACER_RE src/Swr/swrRace.c:3403-3406: on a Fall surface, respawn at once "
                             "(no ground at all takes >3 s, 3439-3448)"))

    course.spline(model)

    entries = []
    for e in ex:
        s0, s1 = course.station_range(e["name"])
        smp = course.frame(s0)
        h = smp['heading']
        fwd = Vector((math.cos(h), math.sin(h), 0))
        left = Vector((-fwd.y, fwd.x, 0))
        at = smp['pos'] + left * (smp['width'] / 2 + 200) + fwd * 100
        bits = " ".join(e["flags"] + e["special"]) or "-"
        signs.sign(f"sign_{e['name']}", [e["title"], *e["lines"], bits.upper()[:18]], tuple(at), (-fwd.x, -fwd.y),
                   track, sign_mat)
        predict = dict(e["predict"])
        if e["flags"] or e["special"]:
            # parity: exactly the bits set in Blender reach the game
            predict.setdefault("surf", surface_bits(e["flags"]))
            predict.setdefault("spec", sum(SPEC[s] for s in e["special"]))
        if e["name"] == "fall":
            predict.pop("surf", None)   # the pod is in the air over the pit for most of it
            predict.pop("spec", None)
        entries.append({"name": e["name"], "s": [round(s0, 1), round(s1, 1)],
                        "measure": ["surface", "air"] if e["name"] == "fall" else ["surface"],
                        "predict": predict, "source": e["source"]})
    return model, {"level": "museum_surfaces", "length": round(course.length, 1),
                   "centerline": course.describe(), "stations": entries, "lap": {"finishes": True}}
