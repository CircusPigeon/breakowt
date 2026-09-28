"""Check the nav graph: every node reachable from every other (with doors open), and report paths
between important spots. Run under a virtual display like the other tools."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402


def main():
    app, g = harness.boot(size=(320, 180))
    from ursina import application
    application.base.win.setActive(False)
    w = g.world
    for d in w.doors.values():
        d.set_open(True, instant=True)
    for k in ("moohole", "shed_board", "cattle_grid"):
        w.colliders[k].enabled = False
    N = w.nav_nodes
    E = w.nav_edges
    seen = {0}
    stack = [0]
    while stack:
        i = stack.pop()
        for j in E[i]:
            if j not in seen:
                seen.add(j)
                stack.append(j)
    bad = [N[i] for i in range(len(N)) if i not in seen]
    print("nodes", len(N), "unreachable:", bad)
    isolated = [N[i] for i in range(len(N)) if not E[i]]
    print("isolated:", isolated)
    Y, L = 0.3, 3.2
    spots = {
        "pasture": (-40, 0, -30), "shed_in": (-7.5, 0, -22), "loft": (17, L, 10), "coop": (44, 0, -36),
        "living": (50, Y, 35), "kitchen": (62, Y, 35), "office": (48, Y, 44.8), "bedroom": (56.4, Y, 43.9),
        "bath": (65, Y, 45), "porch": (54.5, Y, 27.3), "gate": (0, 0, 80), "outside": (0, 0, 100),
    }
    fails = 0
    names = list(spots)
    for a in names:
        for b in names:
            if a >= b:
                continue
            path = w.find_path(spots[a], spots[b])
            # a path is good if every consecutive leg is clear
            pts = [spots[a]] + path
            bad_leg = None
            for i in range(len(pts) - 1):
                if abs(pts[i][1] - pts[i + 1][1]) > 0.5:
                    continue
                if not w._segment_clear(pts[i], pts[i + 1], 0.4):
                    bad_leg = (pts[i], pts[i + 1])
                    break
            if bad_leg:
                fails += 1
                r = lambda p: (round(p[0], 1), round(p[1], 1), round(p[2], 1))
                print(f"NO PATH {a} -> {b}: blocked leg {r(bad_leg[0])} -> {r(bad_leg[1])}")
    print("path failures:", fails)
    return 1 if (bad or fails) else 0


if __name__ == "__main__":
    sys.exit(main())
