"""Custom lighting: one sun, hemispheric ambient, fog, a flashlight and 4 lamps.

Global uniforms live on the render root and are inherited by every entity
using FARM_SHADER. Time-of-day presets are blended by Environment.
"""
from __future__ import annotations

import math

from panda3d.core import (BitMask32, DirectionalLight, PTA_LVecBase4f, RenderState, ShaderAttrib,
                          Vec3 as PVec3, Vec4 as PVec4)
from ursina import Entity, Shader, Vec3, application, camera, color

VERT = """
#version 140
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec2 p3d_MultiTexCoord0;
in vec4 p3d_Color;
uniform vec2 texture_scale;
uniform vec2 texture_offset;
uniform float u_sway;
uniform float u_time;
uniform mat4 p3d_ModelViewMatrix;
uniform struct p3d_LightSourceParameters {
    vec4 color;
    sampler2DShadow shadowMap;
    mat4 shadowViewMatrix;
} p3d_LightSource[1];
out vec2 uv;
out vec3 wpos;
out vec3 wnorm;
out vec4 vcol;
out vec4 shadow_coord;
void main() {
    vec4 v = p3d_Vertex;
    if (u_sway > 0.0) {
        // wind: displacement grows with height above the ground
        float h = max(v.y, 0.0);
        float ph = u_time * 1.6 + v.x * 0.31 + v.z * 0.23;
        v.x += (sin(ph) + 0.35 * sin(ph * 2.7)) * u_sway * h;
        v.z += cos(ph * 0.83) * u_sway * h * 0.6;
    }
    gl_Position = p3d_ModelViewProjectionMatrix * v;
    uv = p3d_MultiTexCoord0 * texture_scale + texture_offset;
    wpos = (p3d_ModelMatrix * v).xyz;
    wnorm = mat3(p3d_ModelMatrix) * p3d_Normal;
    vcol = p3d_Color;
    // look the shadow up from a point nudged along the normal to avoid self-shadowing acne
    vec4 vs = v + vec4(normalize(p3d_Normal) * 0.05, 0.0);
    shadow_coord = p3d_LightSource[0].shadowViewMatrix * (p3d_ModelViewMatrix * vs);
}
"""

FRAG = """
#version 140
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
in vec2 uv;
in vec3 wpos;
in vec3 wnorm;
in vec4 vcol;
uniform vec3 u_sun_dir;
uniform vec3 u_sun_col;
uniform vec3 u_amb_sky;
uniform vec3 u_amb_ground;
uniform vec3 u_fog_col;
uniform vec2 u_fog;
uniform vec3 u_cam;
uniform vec3 u_flash_pos;
uniform vec3 u_flash_dir;
uniform vec4 u_flash;
uniform vec4 u_lamp_pos[6];
uniform vec4 u_lamp_col[6];
uniform float u_unlit;
uniform float u_emissive;
uniform float u_water;
uniform float u_time;
uniform vec3 u_sky_top;
uniform vec3 u_sky_hor;
uniform vec3 u_sun_disc;
uniform float u_shadows;
uniform float u_shadow_texel;
uniform struct p3d_LightSourceParameters {
    vec4 color;
    sampler2DShadow shadowMap;
    mat4 shadowViewMatrix;
} p3d_LightSource[1];
in vec4 shadow_coord;
out vec4 frag;

float sun_visibility() {
    if (u_shadows < 0.5 || shadow_coord.w <= 0.0) return 1.0;
    vec3 sc = shadow_coord.xyz / shadow_coord.w;
    float edge = min(min(sc.x, 1.0 - sc.x), min(sc.y, 1.0 - sc.y));
    if (edge <= 0.0 || sc.z >= 1.0) return 1.0;
    sc.z -= 0.0008;
    float o = u_shadow_texel * 1.2;
    float s = texture(p3d_LightSource[0].shadowMap, vec3(sc.xy + vec2(-o, -o), sc.z));
    s += texture(p3d_LightSource[0].shadowMap, vec3(sc.xy + vec2(o, -o), sc.z));
    s += texture(p3d_LightSource[0].shadowMap, vec3(sc.xy + vec2(-o, o), sc.z));
    s += texture(p3d_LightSource[0].shadowMap, vec3(sc.xy + vec2(o, o), sc.z));
    s *= 0.25;
    // fade out towards the edge of the shadowed area so there's no hard line
    return mix(1.0, s, smoothstep(0.0, 0.06, edge));
}

float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise2(vec2 p) {
    vec2 i = floor(p); vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash2(i), hash2(i + vec2(1, 0)), f.x), mix(hash2(i + vec2(0, 1)), hash2(i + vec2(1, 1)), f.x), f.y);
}

vec3 tonemap(vec3 c) {
    // gentle filmic shoulder so bright sun and lamps roll off instead of clipping
    c = max(c, vec3(0.0));
    vec3 t = c * (1.0 + c / 5.0) / (1.0 + c);
    t = mix(c, t, 0.55);
    float l = dot(t, vec3(0.299, 0.587, 0.114));
    return mix(vec3(l), t, 1.08);
}

void main() {
    vec4 base = texture(p3d_Texture0, uv) * p3d_ColorScale * vcol;
    if (base.a < 0.03) discard;
    vec3 n = normalize(wnorm);
    if (!gl_FrontFacing) n = -n;
    vec3 V = normalize(u_cam - wpos);
    if (u_water > 0.0) {
        // ripples: perturb the normal with two drifting layers of noise
        vec2 q = wpos.xz * 0.9;
        float e = 0.15;
        float h0 = vnoise2(q + vec2(u_time * 0.35, u_time * 0.2)) + 0.5 * vnoise2(q * 2.3 - vec2(u_time * 0.5, 0.0));
        float hx = vnoise2(q + vec2(e, 0) + vec2(u_time * 0.35, u_time * 0.2)) + 0.5 * vnoise2((q + vec2(e, 0)) * 2.3 - vec2(u_time * 0.5, 0.0));
        float hz = vnoise2(q + vec2(0, e) + vec2(u_time * 0.35, u_time * 0.2)) + 0.5 * vnoise2((q + vec2(0, e)) * 2.3 - vec2(u_time * 0.5, 0.0));
        n = normalize(vec3(-(hx - h0) / e * 0.08, 1.0, -(hz - h0) / e * 0.08));
    }
    float ndl = max(dot(n, u_sun_dir), 0.0);
    float hemi = n.y * 0.5 + 0.5;
    float vis = ndl > 0.0 ? sun_visibility() : 1.0;
    vec3 light = mix(u_amb_ground, u_amb_sky, hemi) + u_sun_col * ndl * vis;
    // contact shadow where upright surfaces meet the ground
    float ao = mix(0.62, 1.0, smoothstep(0.0, 0.85, wpos.y));
    light *= mix(1.0, ao, (1.0 - abs(n.y)) * (1.0 - u_unlit));
    if (u_flash.w > 0.0) {
        vec3 fl = wpos - u_flash_pos;
        float fd = length(fl);
        if (fd < u_flash.z) {
            vec3 fdir = fl / max(fd, 0.001);
            float c = dot(fdir, u_flash_dir);
            float spot = smoothstep(u_flash.x, u_flash.y, c);
            float att = 1.0 - fd / u_flash.z;
            light += vec3(1.0, 0.93, 0.75) * spot * att * u_flash.w * max(dot(n, -fdir), 0.25);
        }
    }
    for (int i = 0; i < 6; i++) {
        float r = u_lamp_pos[i].w;
        if (r > 0.0) {
            vec3 lv = u_lamp_pos[i].xyz - wpos;
            float d = length(lv);
            if (d < r) {
                float att = 1.0 - d / r;
                att *= att;
                light += u_lamp_col[i].rgb * u_lamp_col[i].a * att * (0.35 + 0.65 * max(dot(n, lv / max(d, 0.001)), 0.0));
            }
        }
    }
    vec3 lit = base.rgb * light;
    vec3 col = mix(lit, base.rgb, u_unlit) + base.rgb * u_emissive;
    if (u_water > 0.0) {
        // sky reflection at grazing angles plus a sun glint
        float fres = pow(1.0 - max(dot(n, V), 0.0), 4.0);
        vec3 R = reflect(-V, n);
        vec3 sky = mix(u_sky_hor, u_sky_top, clamp(R.y * 1.6, 0.0, 1.0));
        col = mix(col, sky, 0.18 + 0.6 * fres);
        float spec = pow(max(dot(R, u_sun_dir), 0.0), 180.0);
        col += u_sun_disc * spec * 2.2 * u_water * sun_visibility();
    }
    col = tonemap(col);
    float dist = length(wpos - u_cam);
    float f = clamp((dist - u_fog.x) / max(u_fog.y - u_fog.x, 0.01), 0.0, 1.0);
    col = mix(col, u_fog_col, f * f * (3.0 - 2.0 * f));
    frag = vec4(col, base.a);
}
"""

FARM_SHADER = Shader(name="farm_shader", language=Shader.GLSL, vertex=VERT, fragment=FRAG,
                     default_input={"texture_scale": (1, 1), "texture_offset": (0, 0),
                                    "u_unlit": 0.0, "u_emissive": 0.0, "u_sway": 0.0, "u_water": 0.0})

SHADOWS_SUPPORTED = True

_LIGHT_STRUCT = """uniform struct p3d_LightSourceParameters {
    vec4 color;
    sampler2DShadow shadowMap;
    mat4 shadowViewMatrix;
} p3d_LightSource[1];"""


def _strip_shadows(vert, frag):
    """The same shader without Panda's shadow-map struct (some drivers crash on it)."""
    import re
    v = vert.replace(_LIGHT_STRUCT, "").replace(
        "shadow_coord = p3d_LightSource[0].shadowViewMatrix * (p3d_ModelViewMatrix * vs);", "shadow_coord = vec4(0.0);")
    f = frag.replace(_LIGHT_STRUCT, "")
    f = re.sub(r"float sun_visibility\(\) \{.*?\n\}\n", "float sun_visibility() { return 1.0; }\n", f, flags=re.S)
    assert "p3d_LightSource" not in v + f, "shadow struct still referenced"
    return v, f


def set_shadow_support(ok):
    """Call before any entity uses FARM_SHADER. Without support the shadow-free variant is used."""
    global SHADOWS_SUPPORTED
    SHADOWS_SUPPORTED = bool(ok)
    if not ok:
        FARM_SHADER.vertex, FARM_SHADER.fragment = _strip_shadows(VERT, FRAG)
    else:
        FARM_SHADER.vertex, FARM_SHADER.fragment = VERT, FRAG
    FARM_SHADER.compiled = False


DEPTH_VERT = """
#version 140
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
in vec4 p3d_Color;
uniform float u_sway;
uniform float u_time;
uniform vec2 texture_scale;
uniform vec2 texture_offset;
out vec2 uv;
out float valpha;
void main() {
    vec4 v = p3d_Vertex;
    if (u_sway > 0.0) {
        float h = max(v.y, 0.0);
        float ph = u_time * 1.6 + v.x * 0.31 + v.z * 0.23;
        v.x += (sin(ph) + 0.35 * sin(ph * 2.7)) * u_sway * h;
        v.z += cos(ph * 0.83) * u_sway * h * 0.6;
    }
    gl_Position = p3d_ModelViewProjectionMatrix * v;
    uv = p3d_MultiTexCoord0 * texture_scale + texture_offset;
    valpha = p3d_Color.a;
}
"""

DEPTH_FRAG = """
#version 140
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
in vec2 uv;
in float valpha;
out vec4 frag;
void main() {
    if (texture(p3d_Texture0, uv).a * p3d_ColorScale.a * valpha < 0.5) discard;
    frag = vec4(1.0);
}
"""

SKY_VERT = """
#version 140
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
out vec3 wpos;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    wpos = (p3d_ModelMatrix * p3d_Vertex).xyz;
}
"""

SKY_FRAG = """
#version 140
in vec3 wpos;
uniform vec3 u_cam;
uniform vec3 u_sun_dir;
uniform vec3 u_sky_top;
uniform vec3 u_sky_hor;
uniform vec3 u_sky_ground;
uniform vec3 u_sun_disc;
uniform float u_stars;
uniform float u_clouds;
uniform float u_time;
uniform float u_moon;
out vec4 frag;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) {
    vec2 i = floor(p); vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}
void main() {
    vec3 d = normalize(wpos - u_cam);
    float h = d.y;
    vec3 col = mix(u_sky_hor, u_sky_top, pow(clamp(h, 0.0, 1.0), 0.55));
    col = mix(col, u_sky_ground, clamp(-h * 5.0, 0.0, 1.0));
    float sd = max(dot(d, u_sun_dir), 0.0);
    float disc = u_moon > 0.5 ? smoothstep(0.9993, 0.9996, sd) : smoothstep(0.9990, 0.9994, sd);
    col += u_sun_disc * (disc * 2.5 + pow(sd, 10.0) * 0.3 + pow(sd, 90.0) * 0.4);
    if (u_stars > 0.0 && h > 0.0) {
        vec2 sp = d.xz / (d.y + 0.35) * 220.0;
        float s = hash(floor(sp));
        float tw = 0.6 + 0.4 * sin(u_time * 3.0 + s * 50.0);
        col += vec3(step(0.9965, s) * u_stars * tw * clamp(h * 4.0, 0.0, 1.0));
    }
    if (u_clouds > 0.0 && h > 0.0) {
        vec2 cp = d.xz / (h + 0.12) * 1.6 + vec2(u_time * 0.012, u_time * 0.004);
        float c = vnoise(cp) * 0.55 + vnoise(cp * 2.1) * 0.3 + vnoise(cp * 4.3) * 0.15;
        c = smoothstep(1.0 - u_clouds, 1.05 - u_clouds * 0.6, c) * clamp(h * 6.0, 0.0, 1.0);
        vec3 ccol = mix(u_sky_hor * 1.05 + vec3(0.08), u_sun_disc * 0.25 + u_sky_top * 0.6, 0.35);
        col = mix(col, ccol, c * 0.85);
    }
    frag = vec4(col, 1.0);
}
"""

SKY_SHADER = Shader(name="sky_shader", language=Shader.GLSL, vertex=SKY_VERT, fragment=SKY_FRAG)


def _v(c):
    return PVec3(float(c[0]), float(c[1]), float(c[2]))


def sun_vector(elev_deg, azim_deg):
    e, a = math.radians(elev_deg), math.radians(azim_deg)
    return (math.cos(e) * math.sin(a), math.sin(e), math.cos(e) * math.cos(a))


def hexc(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


PRESETS = {
    "dawn": dict(sky_top=hexc("3b5a8f"), sky_hor=hexc("f2a36b"), sky_ground=hexc("5a4a45"),
                 sun=(6, 80), sun_col=(1.0, 0.62, 0.38), sun_disc=(1.0, 0.7, 0.45),
                 amb_sky=(0.42, 0.42, 0.55), amb_ground=(0.28, 0.24, 0.24), fog=hexc("d9a07c"),
                 fog_near=40, fog_far=230, stars=0.15, clouds=0.35, moon=0),
    "morning": dict(sky_top=hexc("4f8fd6"), sky_hor=hexc("cfe3f2"), sky_ground=hexc("7a8a70"),
                    sun=(28, 110), sun_col=(1.0, 0.93, 0.78), sun_disc=(1.0, 0.95, 0.8),
                    amb_sky=(0.50, 0.55, 0.65), amb_ground=(0.33, 0.32, 0.26), fog=hexc("c8dcea"),
                    fog_near=60, fog_far=280, stars=0.0, clouds=0.38, moon=0),
    "noon": dict(sky_top=hexc("3f86d8"), sky_hor=hexc("bcd9f0"), sky_ground=hexc("7a8a70"),
                 sun=(60, 170), sun_col=(1.0, 0.97, 0.9), sun_disc=(1.0, 1.0, 0.9),
                 amb_sky=(0.52, 0.56, 0.64), amb_ground=(0.34, 0.33, 0.27), fog=hexc("bcd6ea"),
                 fog_near=70, fog_far=300, stars=0.0, clouds=0.42, moon=0),
    "overcast": dict(sky_top=hexc("8a929c"), sky_hor=hexc("b9bec4"), sky_ground=hexc("6a6e68"),
                     sun=(45, 150), sun_col=(0.45, 0.46, 0.48), sun_disc=(0.25, 0.25, 0.25),
                     amb_sky=(0.62, 0.64, 0.68), amb_ground=(0.40, 0.40, 0.38), fog=hexc("aeb3b8"),
                     fog_near=30, fog_far=190, stars=0.0, clouds=0.9, moon=0),
    "rain": dict(sky_top=hexc("5d646e"), sky_hor=hexc("858b92"), sky_ground=hexc("4d524e"),
                 sun=(40, 150), sun_col=(0.3, 0.31, 0.34), sun_disc=(0.1, 0.1, 0.1),
                 amb_sky=(0.48, 0.5, 0.55), amb_ground=(0.30, 0.31, 0.30), fog=hexc("7d838a"),
                 fog_near=15, fog_far=140, stars=0.0, clouds=1.0, moon=0),
    "sunset": dict(sky_top=hexc("35477e"), sky_hor=hexc("f08a4b"), sky_ground=hexc("4a3a38"),
                   sun=(7, 250), sun_col=(1.0, 0.55, 0.3), sun_disc=(1.0, 0.6, 0.35),
                   amb_sky=(0.42, 0.38, 0.5), amb_ground=(0.30, 0.22, 0.2), fog=hexc("d98a64"),
                   fog_near=45, fog_far=240, stars=0.1, clouds=0.4, moon=0),
    "dusk": dict(sky_top=hexc("1e2748"), sky_hor=hexc("7a4a6a"), sky_ground=hexc("2a2430"),
                 sun=(-2, 260), sun_col=(0.35, 0.25, 0.3), sun_disc=(0.6, 0.3, 0.3),
                 amb_sky=(0.26, 0.26, 0.38), amb_ground=(0.14, 0.12, 0.16), fog=hexc("4a3a55"),
                 fog_near=30, fog_far=190, stars=0.5, clouds=0.3, moon=0),
    "night": dict(sky_top=hexc("070b1a"), sky_hor=hexc("1c2744"), sky_ground=hexc("0b0d14"),
                  sun=(35, 210), sun_col=(0.20, 0.24, 0.36), sun_disc=(0.85, 0.88, 1.0),
                  amb_sky=(0.13, 0.15, 0.25), amb_ground=(0.06, 0.06, 0.09), fog=hexc("111829"),
                  fog_near=20, fog_far=150, stars=1.0, clouds=0.2, moon=1),
    "predawn": dict(sky_top=hexc("0c1430"), sky_hor=hexc("3a3f6a"), sky_ground=hexc("12131c"),
                    sun=(25, 240), sun_col=(0.22, 0.25, 0.38), sun_disc=(0.8, 0.85, 1.0),
                    amb_sky=(0.17, 0.19, 0.30), amb_ground=(0.08, 0.08, 0.12), fog=hexc("1d2440"),
                    fog_near=25, fog_far=160, stars=0.8, clouds=0.25, moon=1),
    "sunrise": dict(sky_top=hexc("5a7fc0"), sky_hor=hexc("ffb37a"), sky_ground=hexc("6a5a50"),
                    sun=(9, 75), sun_col=(1.0, 0.72, 0.45), sun_disc=(1.0, 0.8, 0.5),
                    amb_sky=(0.50, 0.48, 0.58), amb_ground=(0.32, 0.27, 0.26), fog=hexc("f0b88c"),
                    fog_near=50, fog_far=320, stars=0.0, clouds=0.35, moon=0),
    "interior": dict(sky_top=hexc("4f8fd6"), sky_hor=hexc("cfe3f2"), sky_ground=hexc("7a8a70"),
                     sun=(28, 110), sun_col=(0.6, 0.55, 0.45), sun_disc=(1.0, 0.95, 0.8),
                     amb_sky=(0.5, 0.48, 0.45), amb_ground=(0.3, 0.28, 0.25), fog=hexc("c8dcea"),
                     fog_near=60, fog_far=280, stars=0.0, clouds=0.38, moon=0),
}

_KEYS_VEC = ["sky_top", "sky_hor", "sky_ground", "sun_col", "sun_disc", "amb_sky", "amb_ground", "fog"]
_KEYS_F = ["fog_near", "fog_far", "stars", "clouds", "moon"]


def _lerp(a, b, t):
    return a + (b - a) * t


SHADOW_MASK = BitMask32.bit(1)
SHADOW_SIZE = 2048
SHADOW_FILM = 110.0


def no_shadow(np):
    """Keep a node out of the sun's shadow pass (glass, wire mesh, decals, text)."""
    np.hide(SHADOW_MASK)


class Environment:
    """Owns global lighting uniforms, the sky dome, the sun's shadow map and time-of-day blending."""

    def __init__(self, shadows=True):
        self.render = application.base.render
        # the main camera must not use the shadow bit, or hiding things from the sun would hide them from us
        application.base.cam.node().setCameraMask(BitMask32.bit(0))
        self.sun_np = None
        self.shadows = False
        self.state = dict(PRESETS["morning"])
        self.state["sun_vec"] = sun_vector(*self.state["sun"])
        self._from = None
        self._to = None
        self._t = 1.0
        self._dur = 1.0
        self.time = 0.0
        self.flash = None  # (pos, dir, cos_outer, cos_inner, range, intensity)
        self.lamps: dict[str, tuple] = {}
        self.brightness = 1.0
        self.sky = Entity(model="sphere", scale=900, double_sided=True, shader=SKY_SHADER,
                          eternal=False)
        self.sky.setBin("background", 0)
        self.sky.setDepthWrite(False)
        self.sky.setDepthTest(False)
        no_shadow(self.sky)
        self.set_shadows(shadows)
        self._apply()

    def set_shadows(self, on):
        on = bool(on) and SHADOWS_SUPPORTED
        r = self.render
        if on and self.sun_np is None:
            try:
                light = DirectionalLight("sun")
                light.setShadowCaster(True, SHADOW_SIZE, SHADOW_SIZE)
                light.setCameraMask(SHADOW_MASK)
                lens = light.getLens()
                lens.setFilmSize(SHADOW_FILM, SHADOW_FILM)
                lens.setNearFar(1.0, 400.0)
                from panda3d.core import Shader as PShader
                depth = PShader.make(PShader.SL_GLSL, DEPTH_VERT, DEPTH_FRAG)
                light.setInitialState(RenderState.make(ShaderAttrib.make(depth, 1000)))
                self.sun_np = r.attachNewNode(light)
                r.setLight(self.sun_np)
            except Exception as e:  # no shadow support: carry on without
                print("shadows unavailable:", e)
                self.sun_np = None
                on = False
        elif not on and self.sun_np is not None:
            r.clearLight(self.sun_np)
            self.sun_np.removeNode()
            self.sun_np = None
        self.shadows = on
        r.set_shader_input("u_shadows", 1.0 if on else 0.0)
        r.set_shader_input("u_shadow_texel", 1.0 / SHADOW_SIZE)

    def _place_sun(self):
        """Keep the shadow frustum centred on the camera, snapped to whole texels so edges don't crawl."""
        if self.sun_np is None:
            return
        cam = camera.world_position
        sv = self.state["sun_vec"]
        # below the horizon at night: use the moon's direction as the preset gives it
        d = (float(sv[0]), float(sv[1]), float(sv[2]))
        if d[1] < 0.08:
            d = (d[0], 0.08, d[2])
        step = SHADOW_FILM / SHADOW_SIZE * 4
        cx = round(cam.x / step) * step
        cz = round(cam.z / step) * step
        center = PVec3(cx, 0.0, cz)
        self.sun_np.setPos(center + PVec3(*d) * 200.0)
        self.sun_np.lookAt(center)

    def set_preset(self, name, duration=0.0):
        target = dict(PRESETS[name])
        target["sun_vec"] = sun_vector(*target["sun"])
        if duration <= 0:
            self.state = target
            self._t = 1.0
            self._to = None
        else:
            self._from = dict(self.state)
            self._to = target
            self._t = 0.0
            self._dur = duration
        self.preset_name = name

    def set_lamp(self, key, pos=None, radius=0.0, col=(1, 0.8, 0.5), intensity=1.0):
        if pos is None or radius <= 0:
            self.lamps.pop(key, None)
        else:
            self.lamps[key] = (tuple(pos), radius, tuple(col), intensity)

    def update(self, dt):
        self.time += dt
        if self._to is not None:
            self._t = min(1.0, self._t + dt / self._dur)
            t = self._t * self._t * (3 - 2 * self._t)
            s = {}
            for k in _KEYS_VEC:
                s[k] = tuple(_lerp(a, b, t) for a, b in zip(self._from[k], self._to[k]))
            for k in _KEYS_F:
                s[k] = _lerp(self._from[k], self._to[k], t)
            sv = [_lerp(a, b, t) for a, b in zip(self._from["sun_vec"], self._to["sun_vec"])]
            m = math.sqrt(sum(x * x for x in sv)) or 1
            s["sun_vec"] = tuple(x / m for x in sv)
            s["sun"] = self._to["sun"]
            self.state = s
            if self._t >= 1.0:
                self.state = self._to
                self._to = None
        self._apply()

    def _apply(self):
        s = self.state
        r = self.render
        b = self.brightness
        r.set_shader_input("u_sun_dir", _v(s["sun_vec"]))
        r.set_shader_input("u_sun_col", _v([c * b for c in s["sun_col"]]))
        r.set_shader_input("u_amb_sky", _v([c * b for c in s["amb_sky"]]))
        r.set_shader_input("u_amb_ground", _v([c * b for c in s["amb_ground"]]))
        r.set_shader_input("u_fog_col", _v(s["fog"]))
        r.set_shader_input("u_fog", (float(s["fog_near"]), float(s["fog_far"])))
        cam = camera.world_position
        r.set_shader_input("u_cam", PVec3(cam.x, cam.y, cam.z))
        r.set_shader_input("u_sky_top", _v(s["sky_top"]))
        r.set_shader_input("u_sky_hor", _v(s["sky_hor"]))
        r.set_shader_input("u_sky_ground", _v(s["sky_ground"]))
        r.set_shader_input("u_sun_disc", _v(s["sun_disc"]))
        r.set_shader_input("u_stars", float(s["stars"]))
        r.set_shader_input("u_clouds", float(s["clouds"]))
        r.set_shader_input("u_moon", float(s["moon"]))
        r.set_shader_input("u_time", float(self.time))
        if self.flash:
            pos, d, co, ci, rng, inten = self.flash
            r.set_shader_input("u_flash_pos", PVec3(*pos))
            r.set_shader_input("u_flash_dir", PVec3(*d))
            r.set_shader_input("u_flash", PVec4(co, ci, rng, inten))
        else:
            r.set_shader_input("u_flash_pos", PVec3(0, -100, 0))
            r.set_shader_input("u_flash_dir", PVec3(0, -1, 0))
            r.set_shader_input("u_flash", PVec4(0.9, 0.95, 1.0, 0.0))
        lp = PTA_LVecBase4f()
        lc = PTA_LVecBase4f()
        # the 6 closest lamps to the camera
        items = sorted(self.lamps.values(), key=lambda L: (L[0][0] - cam.x) ** 2 + (L[0][2] - cam.z) ** 2)[:6]
        for i in range(6):
            if i < len(items):
                (x, y, z), rad, c, inten = items[i]
                lp.push_back(PVec4(x, y, z, rad))
                lc.push_back(PVec4(c[0], c[1], c[2], inten))
            else:
                lp.push_back(PVec4(0, 0, 0, 0))
                lc.push_back(PVec4(0, 0, 0, 0))
        r.set_shader_input("u_lamp_pos", lp)
        r.set_shader_input("u_lamp_col", lc)
        self.sky.position = cam
        self._place_sun()

    @property
    def is_dark(self):
        s = self.state
        return (s["amb_sky"][0] + s["sun_col"][0]) < 0.6
