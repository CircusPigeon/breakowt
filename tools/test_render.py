"""Render a tiny test scene and save a screenshot (engine smoke test)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from breakowt.engine.boot import create_app, screenshot
app = create_app(windowed=True, size=(1280, 800))
from ursina import Entity, camera, application
from breakowt.engine.shading import FARM_SHADER, Environment
from breakowt.engine.meshbuilder import MeshBuilder
from breakowt.engine.assets import tex
env = Environment()
env.set_preset(sys.argv[2] if len(sys.argv) > 2 else "morning")
g = MeshBuilder().ground(-50, -50, 50, 50, color=(1, 1, 1, 1), uv_density=0.25)
Entity(model=g.build(), texture=tex("grass"), shader=FARM_SHADER)
b = MeshBuilder()
b.box((0, 1.5, 8), (6, 3, 4), uv_density=0.5)
b.box((4, 1, 12), (2, 2, 2), rot=(0, 35, 0))
Entity(model=b.build(), texture=tex("barn_red"), shader=FARM_SHADER)
c = MeshBuilder()
c.cylinder((-5, 0, 10), 1.0, 3.0, color=(0.8, 0.8, 0.85, 1), segs=16)
c.sphere((-2, 1, 5), 0.8, color=(1, 1, 1, 1), segs=14, rings=10)
c.cone((6, 0, 6), 1, 2, color=(0.9, 0.3, 0.2, 1))
Entity(model=c.build(), texture=tex("cowhide"), shader=FARM_SHADER)
s = MeshBuilder().quad((0, 1.5, 5.9), (3, 1.2), rot=(0, 0, 0))
Entity(model=s.build(), texture=tex("sign_farm"), shader=FARM_SHADER)
camera.position = (0, 1.6, -4)
camera.rotation = (8, 0, 0)
camera.fov = 75
n = {"f": 0}
def upd(task):
    env.update(1/60)
    n["f"] += 1
    if n["f"] == 20:
        out = sys.argv[1] if len(sys.argv) > 1 else "screenshots/test.png"
        os.makedirs(os.path.dirname(out), exist_ok=True)
        print("shot", screenshot(out))
        app.userExit()
    return task.cont
application.base.taskMgr.add(upd, "t")
app.run()
