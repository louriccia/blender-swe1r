"""The smallest track that should race: a flat stadium loop.

It exists to prove the from-scratch path (new scene -> export -> custom track -> race) before any
other level depends on it.
"""
import course as C
import lib


def build(addon):
    model, track, sky = lib.new_track_scene(addon)
    road_mat = lib.material(addon, "road", lib.checker_image("road_checker"))
    course = C.exhibit_loop([("straight", 4000.0)], radius=2000.0)
    for objs in course.road(track, road_mat).values():
        for obj in objs:
            lib.shade(obj)
    lib.spline("spline", course.spline_points(), model)
    return model, {"level": "hello", "length": round(course.length, 1), "centerline": course.describe(),
                   "stations": [], "lap": {"finishes": True}}
