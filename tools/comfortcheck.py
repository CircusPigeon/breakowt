"""Render enlarged reading layouts and check paging/input and first-person comfort controls.

Uses the isolated save directory supplied by harness; pass width and height to check another aspect.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness


def main():
    size = tuple(map(int, sys.argv[1:3])) if len(sys.argv) > 2 else (1200, 800)
    app, g = harness.boot(size=size)
    from ursina import camera, held_keys
    from breakowt.days import PLANNER, SPREADSHEET, LEDGER, EMAILS
    from breakowt.items import ITEMS
    from breakowt.ui import text_width, text_pages

    # Story scraps contain inequalities and literal angle brackets: these are ink, not text tags.
    import breakowt.days as days
    for font in g.ui.fonts.values():
        for value in vars(days).values():
            if isinstance(value, str) and value:
                text_pages(value, 0.8, 0.6, 1.3, font)
    assert text_width("3 10/71 < round / across < 3 1/7", 1.3, g.ui.fonts.get("hand")) > 0

    ui = g.ui
    g.runner.stop_all()
    g.state = "play"
    g.cutscene = g.cam_free = g.in_dialogue = False
    ui.set_fade(0)
    ui.title_card("")
    g.day_title, g.day_sub = "MONDAY", "The Fence · 6 days until steak"
    for key in list(ITEMS)[:18]:
        g.inv.add(key, silent=True)
    g.objective_lines = lambda: [("Meet Moocrates and find a way out of the pasture.", True),
                                 ("Help Archimoodes repair the fence before Chuck wakes up.", False),
                                 ("Introduce yourself to the other cows around the farm.", False)]
    g.side_quest_lines = lambda: [("Find Moothagoras' missing page and bring it back.", "active"),
                                 ("Bring a shiny thing to Cluckydides.", "active")]
    for scale in (1.0, 1.3):
        ui.reading_scale = scale
        suffix = f"{size[0]}x{size[1]}_{int(scale * 100)}"
        for tab in ("sound", "comfort"):
            ui.open_settings(lambda: None, tab)
            ui.aspect -= 0.01
            ui.relayout()
            assert ui._modal_state["tab"] == tab
            harness.shot(app, f"comfort_settings_{tab}_{suffix}")
        for name, body, style in (("Chuck's planner", PLANNER, "paper"),
                                  ("Under the doormat", "Spare key is under the FLOWERPOT.", "note"),
                                  ("COWS.XLS - ChuckOffice", SPREADSHEET, "screen"),
                                  ("HAPPY ACRES PROCESSING - INTAKE", LEDGER, "ledger")):
            ui.show_document(name, body, style=style)
            st = ui._modal_state
            for page in range(len(st["pages"])):
                assert st["page"] == page
                harness.shot(app, f"comfort_doc_{style}_{suffix}_{page + 1}")
                g._modal_input("right arrow")
            assert not ui.document_input("right arrow")
            assert st["page"] == len(st["pages"]) - 1
            ui.aspect -= 0.01
            ui.relayout()
            assert ui._modal_state["page"] == st["page"]
            assert ui.document_input("space")
        ui.open_journal(g)
        st = ui._modal_state
        assert st["count"] > 1, "A large inventory must have accessible pages."
        for page in range(st["count"]):
            assert st["page"] == page
            harness.shot(app, f"comfort_journal_{suffix}_{page + 1}")
            g._modal_input("right arrow")
        ui.aspect -= 0.01
        ui.relayout()
        assert ui._modal_state["page"] == st["page"]
        assert ui.journal_input("tab")
        ui.open_mail(EMAILS)
        for i in range(len(EMAILS)):
            ui._mail_pick(i)
            st = ui._modal_state
            for page in range(len(st["pages"])):
                harness.shot(app, f"comfort_mail_{suffix}_{i + 1}_{page + 1}")
                ui.mail_input("right arrow")
        ui.aspect -= 0.01
        ui.relayout()
        assert ui._modal_state["sel"] == len(EMAILS) - 1
        ui.close_modal()
        line = ("The fence needs our attention. Chuck sleeps nearby; move quietly and watch where he looks. " * 12).strip()
        ui.dlg_show("Moocrates", line)
        g.in_dialogue = True
        g._advance = False
        assert len(ui.dlg_pages) > 1
        while True:
            g.input("space")
            assert ui.dlg_page_revealed()
            harness.shot(app, f"comfort_dialogue_{suffix}_{ui.dlg_page + 1}")
            old_page = ui.dlg_page
            g.input("space")
            if ui.dlg_page == old_page:
                assert g._advance
                break
            assert not g._advance
        assert ui.dlg_revealed()
        ui.show_choices(["Help repair the fence.", "Look around the farm first."])
        ui.aspect -= 0.01
        ui.relayout()
        assert ui.dlg_revealed() and ui.choice_root.enabled
        harness.shot(app, f"comfort_choices_{suffix}")
        assert min(b.y - b.scale_y / 2 for b in ui.choice_items) > ui.dlg_top
        ui.clear_choices()
        ui.dlg_hide()
        g.in_dialogue = False

    # Measured wrapping also handles long unbroken words.
    pages = text_pages("W" * 200, 0.4, 0.25, 1.3)
    assert len(pages) > 1
    assert "".join(pages).replace("\n", "") == "W" * 200
    assert all(text_width(line, 1.3) <= 0.4 + 1e-6 for page in pages for line in page.split("\n"))
    p = g.player
    settings = {"fov_base": 105.0, "camera_bob": 0.0, "camera_roll": 0.5,
                "camera_shake": 0.0, "sprint_fov": False, "sensitivity": 1.45, "invert_y": True}
    for field, value in settings.items():
        setattr(p, field, value)
    ui.reading_scale = 1.15
    g.audio.volumes["music"] = 0.35
    assert g.save_settings()
    for field in settings:
        setattr(p, field, 0)
    ui.reading_scale = 1.0
    g.audio.volumes["music"] = 0.0
    g.load_settings()
    assert all(getattr(p, field) == value for field, value in settings.items())
    assert ui.reading_scale == 1.15 and g.audio.volumes["music"] == 0.35
    p.frozen = p.look_frozen = False
    p.camera_bob = p.camera_roll = p.camera_shake = 0.0
    p.sprint_fov = False
    p.fov_base = 95.0
    p.shake, p.lunge = 0.5, 1.0
    camera.fov = p.fov_base
    held_keys["w"] = held_keys["shift"] = 1
    p.update(1 / 30)
    assert abs(p.head.y - p.cam_y) < 1e-6
    assert abs(p.head.rotation_z) < 1e-6
    assert abs(camera.z) < 1e-6
    assert abs(camera.fov - p.fov_base) < 1e-6
    held_keys["w"] = held_keys["shift"] = 0
    from breakowt.vehicle import Tractor
    tractor = Tractor(g, g.world.tractor)
    tractor.enter()
    tractor.speed, tractor.shake, tractor.puff_t = 3.0, 0.8, 10.0
    g.env.time = 1.0
    camera.fov = 80.0
    tractor.update(1 / 30)
    assert abs(tractor.ent.rotation_z) < 1e-6
    assert abs(tractor.seat.rotation_x - tractor.look_pitch) < 1e-6
    for _ in range(60):
        tractor.update(1 / 30)
    assert abs(camera.fov - p.fov_base) < 0.001
    tractor.leave()
    assert not p.driving and camera.parent == p.head
    print(f"Comfort/readability checks passed at {size[0]}x{size[1]}", flush=True)


if __name__ == "__main__":
    main()
