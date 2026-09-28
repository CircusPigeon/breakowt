"""Quick smoke test: title screen, then a day, with dialogue auto-advanced. Prints script errors."""
import sys
import time as _t
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402

day = int(sys.argv[1]) if len(sys.argv) > 1 else 1
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 20
app, g = harness.boot()
errors = []
orig = g._script_error


def on_err(s):
    errors.append((s.name, s.error))
    orig(s)


g.runner.on_error = on_err
g.story.start(0)
harness.step(app, 30)
harness.shot(app, f"smoke_title")
g.story.new_game(day)
t0 = _t.time()
frames = int(secs * 30)
for i in range(frames):
    if g.in_dialogue and g.ui.dlg_revealed():
        g._advance = True
    if g.ui.choice_root.enabled:
        g.ui.choice_result = 0
    if g.ui.modal == "document":
        g.ui.close_modal()
        g._doc_closed = True
    app.step()
    if i % 150 == 0:
        harness.shot(app, f"smoke_d{day}_{i // 30:03d}")
print("frames", frames, "time", round(_t.time() - t0, 1), "step", g.story.cur, "state", g.state)
print("objectives", g.objective_lines())
for name, e in errors:
    print("ERROR in", name, e)
