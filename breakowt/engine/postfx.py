"""The 3D scene drawn into an offscreen buffer and put on screen by one full-screen pass.

This lets the scene render below the window's resolution (a big saving on high-DPI laptop
screens, where the window is opened at the panel's full pixel count) while the UI stays sharp,
since the UI has its own display region on top. The pass smooths edges (FXAA) and, when the
scene is upscaled, sharpens a little to make up for the stretch.
"""
from __future__ import annotations

from direct.filter.FilterManager import FilterManager
from panda3d.core import FrameBufferProperties, SamplerState, Texture
from panda3d.core import Shader as PShader

QUAD_VERT = """
#version 140
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
out vec2 texcoord;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    texcoord = p3d_MultiTexCoord0;
}
"""

QUAD_FRAG = """
#version 140
uniform sampler2D u_scene;
uniform float u_fxaa;
uniform float u_sharpen;
in vec2 texcoord;
out vec4 frag;
const vec3 LUMA = vec3(0.299, 0.587, 0.114);
void main() {
    vec2 px = 1.0 / vec2(textureSize(u_scene, 0));
    vec3 m = texture(u_scene, texcoord).rgb;
    if (u_fxaa < 0.5 && u_sharpen <= 0.0) {
        frag = vec4(m, 1.0);
        return;
    }
    vec3 nw = texture(u_scene, texcoord + vec2(-1.0, -1.0) * px).rgb;
    vec3 ne = texture(u_scene, texcoord + vec2(1.0, -1.0) * px).rgb;
    vec3 sw = texture(u_scene, texcoord + vec2(-1.0, 1.0) * px).rgb;
    vec3 se = texture(u_scene, texcoord + vec2(1.0, 1.0) * px).rgb;
    vec3 col = m;
    if (u_fxaa > 0.5) {
        // FXAA (the small console variant): blur along the edge direction, only where there's an edge
        float lnw = dot(nw, LUMA), lne = dot(ne, LUMA), lsw = dot(sw, LUMA), lse = dot(se, LUMA);
        float lm = dot(m, LUMA);
        float lmin = min(lm, min(min(lnw, lne), min(lsw, lse)));
        float lmax = max(lm, max(max(lnw, lne), max(lsw, lse)));
        vec2 dir = vec2(-((lnw + lne) - (lsw + lse)), (lnw + lsw) - (lne + lse));
        float reduce = max((lnw + lne + lsw + lse) * (0.25 / 8.0), 1.0 / 128.0);
        float rcp = 1.0 / (min(abs(dir.x), abs(dir.y)) + reduce);
        dir = clamp(dir * rcp, vec2(-8.0), vec2(8.0)) * px;
        vec3 a = 0.5 * (texture(u_scene, texcoord + dir * (1.0 / 3.0 - 0.5)).rgb +
                        texture(u_scene, texcoord + dir * (2.0 / 3.0 - 0.5)).rgb);
        vec3 b = a * 0.5 + 0.25 * (texture(u_scene, texcoord - dir * 0.5).rgb +
                                   texture(u_scene, texcoord + dir * 0.5).rgb);
        float lb = dot(b, LUMA);
        col = (lb < lmin || lb > lmax) ? a : b;
    }
    if (u_sharpen > 0.0) {
        vec3 blur = (nw + ne + sw + se) * 0.25;
        col = clamp(col + (m - blur) * u_sharpen, 0.0, 1.0);
    }
    frag = vec4(col, 1.0);
}
"""


class _ScaledFilterManager(FilterManager):
    scale = 1.0

    def getScaledSize(self, mul, div, align):
        x, y = FilterManager.getScaledSize(self, mul, div, align)
        return max(16, int(round(x * self.scale))), max(16, int(round(y * self.scale)))


class PostFX:
    """Scene render target + final pass. `ok` is False if the driver refused the buffer; the scene
    then renders straight to the window as before."""

    def __init__(self, base):
        self.base = base
        self.fm = None
        self.quad = None
        self.tex = None
        self.ok = False
        self.scale = 1.0
        self.msaa = 0
        self.fxaa = True

    def apply(self, scale=1.0, msaa=0, fxaa=True):
        scale = max(0.4, min(1.0, float(scale)))
        if self.fm is not None and msaa == self.msaa:
            # same buffer format: just resize and retune the pass
            self.scale = self.fm.scale = scale
            self.fm.resizeBuffers()
            self._set_inputs(fxaa)
            return self.ok
        self.disable()
        self.scale, self.msaa = scale, msaa
        for samples in ((msaa, 0) if msaa else (0,)):
            fm = _ScaledFilterManager(self.base.win, self.base.cam)
            fm.scale = scale
            tex = Texture("scene")
            tex.setWrapU(SamplerState.WM_clamp)
            tex.setWrapV(SamplerState.WM_clamp)
            tex.setMinfilter(SamplerState.FT_linear)
            tex.setMagfilter(SamplerState.FT_linear)
            fbp = FrameBufferProperties()
            fbp.setRgbColor(True)
            fbp.setRgbaBits(8, 8, 8, 8)
            fbp.setDepthBits(24)
            if samples:
                fbp.setMultisamples(samples)
            try:
                quad = fm.renderSceneInto(colortex=tex, fbprops=fbp)
            except Exception as e:      # noqa: BLE001 - any driver refusal means "no post pass"
                print("[breakowt] scene buffer failed:", e, flush=True)
                quad = None
            if quad is not None:
                self.fm, self.quad, self.tex, self.msaa = fm, quad, tex, samples
                quad.setShader(PShader.make(PShader.SL_GLSL, QUAD_VERT, QUAD_FRAG))
                quad.setShaderInput("u_scene", tex)
                self._set_inputs(fxaa)
                self.ok = True
                return True
            fm.cleanup()
        self.ok = False
        return False

    def _set_inputs(self, fxaa):
        self.fxaa = fxaa
        if self.quad is None:
            return
        self.quad.setShaderInput("u_fxaa", 1.0 if fxaa else 0.0)
        # upscaled: sharpen a little, more the further below native the scene is drawn
        self.quad.setShaderInput("u_sharpen", 0.0 if self.scale >= 0.99 else min(0.6, (1.0 - self.scale) * 1.2))

    def disable(self):
        if self.fm is not None:
            self.fm.cleanup()
        self.fm = self.quad = self.tex = None
        self.ok = False

    def internal_size(self):
        win = self.base.win
        if self.fm is None:
            return win.getXSize(), win.getYSize()
        return self.fm.getScaledSize(1, 1, 1)
