"""Coroutine scripts.

A script is a generator. What it yields decides how long it sleeps:
    yield            -> resume next frame
    yield 1.5        -> resume after 1.5 seconds (game time)
    yield cond_fn    -> resume when cond_fn() is truthy
    yield script     -> resume when that Script finishes
Use `yield from sub()` to call sub-scripts and receive their return value.
"""
from __future__ import annotations

import traceback


class Script:
    def __init__(self, gen, name=None, tag=None):
        self.gen = gen
        self.name = name
        self.tag = tag
        self.wait_time = 0.0
        self.wait_cond = None
        self.wait_script = None
        self.done = False
        self.result = None
        self.error = None

    def stop(self):
        if not self.done:
            self.done = True
            try:
                self.gen.close()
            except Exception:
                pass


class ScriptRunner:
    def __init__(self):
        self.scripts: list[Script] = []
        self.on_error = None

    def start(self, gen, name=None, tag=None, replace=True) -> Script:
        if name and replace:
            self.stop(name)
        s = Script(gen, name, tag)
        self.scripts.append(s)
        self._step(s, 0.0)
        return s

    def stop(self, name):
        for s in self.scripts:
            if s.name == name:
                s.stop()
        self.scripts = [s for s in self.scripts if not s.done]

    def stop_tag(self, tag):
        for s in self.scripts:
            if s.tag == tag:
                s.stop()
        self.scripts = [s for s in self.scripts if not s.done]

    def stop_all(self):
        for s in self.scripts:
            s.stop()
        self.scripts = []

    def running(self, name):
        return any(s.name == name and not s.done for s in self.scripts)

    def _step(self, s: Script, dt: float):
        if s.done:
            return
        if s.wait_time > 0:
            s.wait_time -= dt
            if s.wait_time > 0:
                return
        if s.wait_cond is not None:
            try:
                if not s.wait_cond():
                    return
            except Exception:
                s.error = traceback.format_exc()
                s.done = True
                if self.on_error:
                    self.on_error(s)
                return
            s.wait_cond = None
        if s.wait_script is not None:
            if not s.wait_script.done:
                return
            s.wait_script = None
        # advance, possibly several times in one frame if yields are zero waits
        for _ in range(64):
            try:
                val = next(s.gen)
            except StopIteration as e:
                s.done = True
                s.result = e.value
                return
            except Exception:
                s.error = traceback.format_exc()
                s.done = True
                if self.on_error:
                    self.on_error(s)
                return
            if val is None:
                return
            if isinstance(val, (int, float)):
                if val <= 0:
                    return
                s.wait_time = float(val)
                return
            if isinstance(val, Script):
                if val.done:
                    continue
                s.wait_script = val
                return
            if callable(val):
                try:
                    if val():
                        continue
                except Exception:
                    s.error = traceback.format_exc()
                    s.done = True
                    if self.on_error:
                        self.on_error(s)
                    return
                s.wait_cond = val
                return
            return

    def update(self, dt):
        for s in list(self.scripts):
            self._step(s, dt)
        self.scripts = [s for s in self.scripts if not s.done]


def wait(seconds):
    """Sub-generator helper: `yield from wait(2)`."""
    yield seconds


def wait_until(cond):
    yield cond
