"""Screenshots of every UI screen, for eyeballing layout problems."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402


def main():
    app, g = harness.boot(size=(1280, 720))
    s = g.story
    s.new_game(3)
    # skip the day's intro: advance dialogue until the player has had control for a second
    free = 0
    for _ in range(3000):
        if g.in_dialogue and g.ui.dlg_revealed():
            g._advance = True
        app.step()
        free = free + 1 if (g.controls_enabled() and not g.in_dialogue and not g.busy) else 0
        if free > 30:
            break
    g.inv.add("rock", 3, silent=True)
    g.inv.add("radio", silent=True)
    harness.step(app, 3)
    harness.shot(app, "ui_hud")
    g.ui.open_journal(g)
    harness.shot(app, "ui_journal")
    g.ui.close_modal()
    g.open_pause()
    harness.shot(app, "ui_pause")
    g.ui.open_settings(g._back_to_pause)
    harness.shot(app, "ui_settings")
    g.ui.close_modal()
    g.state = "play"
    from breakowt.story import SHOP
    g.ui.open_shop("THE GARDEN", [(k if k != "rock_pouch" else "rock", l, p, d, False) for k, l, p, d in SHOP], 7,
                   lambda k: None, lambda: None)
    harness.shot(app, "ui_shop")
    g.ui.close_modal()
    from breakowt.days import PLANNER, EMAILS, SPREADSHEET, LEDGER
    g.ui.show_document("Chuck's planner", PLANNER)
    harness.shot(app, "ui_doc_paper")
    g.ui.close_modal()
    g.ui.show_document("Under the doormat", "A sticky note, a bit damp:\n\n    Spare key is under the FLOWERPOT.")
    harness.shot(app, "ui_doc_note")
    g.ui.close_modal()
    g.ui.open_mail(EMAILS)
    harness.shot(app, "ui_mail")
    g.ui.close_modal()
    g.ui.show_document("COWS.XLS - ChuckOffice", SPREADSHEET, paper=False)
    harness.shot(app, "ui_doc_screen")
    g.ui.close_modal()
    g.ui.show_document("HAPPY ACRES PROCESSING - INTAKE", LEDGER, style="ledger")
    harness.shot(app, "ui_doc_ledger")
    g.ui.close_modal()
    g.ui.open_moodals(g, lambda: None)
    harness.shot(app, "ui_moodals")
    g.ui.close_modal()
    g.ui.open_combo(3, "Toolbox")
    harness.shot(app, "ui_combo")
    g.ui.close_modal()
    g.ui.open_password()
    g.ui.password_input("b")
    g.ui.password_input("i")
    harness.shot(app, "ui_password")
    g.ui.close_modal()
    g.set_mouse(True)
    g.runner.start(g.say("cowpernicus", "Okay. The plan, final version. I've drawn it again. Moogenes, please. "
                                        "This line is long on purpose, to check that it wraps inside the box.",
                         choices=["Yes. Faint when Chuck comes in.", "Not yet."]), name="t")
    harness.step(app, 90)
    harness.shot(app, "ui_dialogue_choices")
    g.ui.choice_result = 1
    harness.step(app, 3)
    g.end_talk()
    g.ui.set_boss("CHUCK", 0.6)
    g.ui.set_health(2, 3, True)
    g.ui.toast("Got: Tractor Key", "tractor_key")
    g.ui.popup_sub("The ignition is empty. No key. The fuel gauge is resting on E. There's a hole where the spark "
                   "plug should be.")
    g.ui.bark_line("Who's there? Dang raccoons.")
    harness.step(app, 5)
    harness.shot(app, "ui_fight_hud")
    g.ui.set_boss("", 0, False)
    g.ui.set_health(0, 0, False)
    g.ui.letterbox(True)
    g.runner.start(g.card("THURSDAY", "The Truck  ·  3 days until steak", 3.0), name="card")
    harness.step(app, 30)
    harness.shot(app, "ui_card")
    harness.step(app, 80)
    g.ui.letterbox(False)
    g.ui.set_fade(1.0)
    g.runner.start(s.epilogue(), name="epilogue")
    harness.step(app, 60)
    harness.shot(app, "ui_epilogue")
    g.runner.stop("epilogue")
    s.to_title()
    harness.step(app, 40)
    harness.shot(app, "ui_title")
    s.open_title("chapters")
    harness.step(app, 5)
    harness.shot(app, "ui_chapters")


if __name__ == "__main__":
    main()
