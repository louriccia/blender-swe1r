"""The smallest track that should race: a flat stadium loop with low walls.

It exists to prove the from-scratch path (new scene -> export -> custom track -> race) before any
gym station depends on it.
"""
import lib


def build(addon):
    model, track, sky = lib.new_track_scene(addon)
    road_mat = lib.material(addon, "road", lib.checker_image("road_checker"))

    center = lib.stadium(straight=6000, radius=2000, step=400)
    road = lib.ribbon("road", center, 600, track, road_mat, closed=True)
    lib.set_surface(road)
    lib.spline("spline", center, model)
    return model, {"level": "hello", "stations": []}
