"""BREAKOWT: Seven Days to Steak.

    python main.py              fullscreen
    python main.py --windowed   windowed (75% of the screen)
    python main.py --day 3      start on Wednesday (debug)
    python main.py --debug      debug keys: F5 skip step, F6 next day, F7 go to objective,
                                F8 toggle Chuck's eyes, F9 print position
"""
import argparse
import sys


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="BREAKOWT: Seven Days to Steak")
    ap.add_argument("--windowed", action="store_true", help="run in a window instead of fullscreen")
    ap.add_argument("--day", type=int, default=0, help="debug: jump straight to day 1-7")
    ap.add_argument("--debug", action="store_true", help="enable debug keys")
    ap.add_argument("--size", default=None, help="window size, e.g. 1600x900 (with --windowed)")
    return ap.parse_args(argv)


def main():
    args = parse_args()
    from breakowt.app import run
    run(args)


if __name__ == "__main__":
    sys.exit(main())
