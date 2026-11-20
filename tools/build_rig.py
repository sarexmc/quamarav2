#!/usr/bin/env python3
"""
QUMARA rig builder.

Input : tools/source/kumara_geo.bbmodel (modelo original, 5 huesos)
Output: tools/out/kumara_rig.bbmodel          (modelo con huesos + animaciones, ABRIR EN BLOCKBENCH)
        src/main/resources/assets/qumara/geo/entity/qumara.geo.json
        src/main/resources/assets/qumara/animations/entity/qumara.animation.json

Todas las poses se definen en el espacio de Blockbench (lo que se ve en el editor).
ROT_SIGN / POS_SIGN solo afectan al .animation.json generado por este script:
si al exportar desde Blockbench ves que difiere, usa el export de Blockbench (es la referencia).
"""
import json, math, copy, uuid, os, sys, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(HERE, "source", "kumara_geo.bbmodel")
OUT_BB = os.path.join(HERE, "out", "kumara_rig.bbmodel")
OUT_GEO = os.path.join(ROOT, "src/main/resources/assets/qumara/geo/entity/qumara.geo.json")
OUT_ANIM = os.path.join(ROOT, "src/main/resources/assets/qumara/animations/entity/qumara.animation.json")

ROT_SIGN = (-1, -1, 1)   # Blockbench -> archivo .animation.json (rotaciones)
POS_SIGN = (-1, 1, 1)    # Blockbench -> archivo .animation.json (posiciones)

random.seed(7)
def U(): return str(uuid.UUID(int=random.getrandbits(128)))

d = json.load(open(SRC))
G = {x["uuid"]: x for x in d["groups"]}
E = {e["uuid"]: e for e in d["elements"]}
cubes = {G[o["uuid"]]["name"]: [E[c] for c in o["children"] if isinstance(c, str)] for o in d["outliner"]}

# ----------------------------------------------------------------------------------------------
# Estructura de huesos
# ----------------------------------------------------------------------------------------------
bones = {}   # name -> dict(parent, pivot, rot, cubes)
order = []
def bone(name, parent, pivot, cs=None, rot=(0, 0, 0)):
    bones[name] = dict(parent=parent, pivot=list(pivot), rot=list(rot), cubes=cs or [])
    order.append(name)

def center(e):
    return [(e["from"][i] + e["to"][i]) / 2 for i in range(3)]

bone("raiz", None, (0, 0, 0))

# raices: 4 sectores
sect = {"n": [], "s": [], "e": [], "w": []}
for e in cubes["raises"]:
    cx, _, cz = center(e)
    if abs(cx) > abs(cz): sect["e" if cx > 0 else "w"].append(e)
    else: sect["s" if cz > 0 else "n"].append(e)
for k, v in sect.items():
    bone("raices_" + k, "raiz", (0, 6, 0), v)

cu = cubes["cuerto"]
bone("tronco", "raiz", (0, 60, 12), cu[0:4])
bone("tallo_1", "tronco", (-16, 125, 46), cu[4:6])
bone("tallo_2", "tallo_1", (-16, 266, 46), cu[6:])

TONGUE_IDX = {13, 14, 15}
head = [e for i, e in enumerate(cubes["cabeza"]) if i not in TONGUE_IDX]
bone("cabeza", "tronco", (0, 150, -10), head)

for i, e in enumerate(cubes["hojas"], 1):
    bone(f"petalo_{i}", "cabeza", (0, 178, 15), [e])

# lengua: cadena de 8 segmentos de 40 px, apunta hacia -Z
TG_N, TG_L, TG_W, TG_T = 8, 40.0, 12.0, 5.0
tg_origin = (2.0, 168.0, -42.0)
tg_template = copy.deepcopy(cubes["cabeza"][15])
tg_uv = [221, 347, 227, 353]   # parche de la textura del cubo original de la lengua (rosa)
def tongue_cube(i):
    e = copy.deepcopy(tg_template)
    e["name"] = f"lengua_{i+1}"
    e["uuid"] = U()
    x0, y0, z0 = tg_origin
    w = TG_W * (1 - 0.06 * i)
    e["from"] = [x0 - w / 2, y0 - TG_T / 2, z0 - TG_L * (i + 1)]
    e["to"] = [x0 + w / 2, y0 + TG_T / 2, z0 - TG_L * i]
    e["rotation"] = [0, 0, 0]
    e["origin"] = [x0, y0, z0 - TG_L * i]
    for f in e["faces"].values():
        f["uv"] = list(tg_uv); f["texture"] = 0
    return e
for i in range(TG_N):
    par = "cabeza" if i == 0 else f"lengua_{i}"
    bone(f"lengua_{i+1}", par, (tg_origin[0], tg_origin[1], tg_origin[2] - TG_L * i), [tongue_cube(i)],
         rot=(-32, 0, 0) if i == 0 else (0, 0, 0))

# brazos: derecho (original) + izquierdo (espejo)
def mirror(e):
    m = copy.deepcopy(e)
    m["uuid"] = U()
    f, t = e["from"], e["to"]
    m["from"] = [-t[0], f[1], f[2]]; m["to"] = [-f[0], t[1], t[2]]
    if "origin" in e: m["origin"] = [-e["origin"][0], e["origin"][1], e["origin"][2]]
    if e.get("rotation"):
        r = e["rotation"]; m["rotation"] = [r[0], -r[1], -r[2]]
    fc = {}
    for k, v in e["faces"].items():
        nk = {"east": "west", "west": "east"}.get(k, k)
        u = v["uv"]
        fc[nk] = dict(v, uv=[u[2], u[1], u[0], u[3]])
    m["faces"] = fc
    return m

arm = cubes["brazo"]
SEG = [22.7, 60.7, 97.1, 133.4, 169.8]
AY, AZ = 100.0, 16.0
def arm_split(cs):
    segs = [[] for _ in range(5)]
    fingers = {"a": [], "b": [], "c": []}
    for e in cs:
        fx = e["from"][0]
        if fx < SEG[4] - 0.01:
            idx = max(i for i in range(4) if fx >= SEG[i] - 0.01)
            segs[idx].append(e)
        else:
            cz = center(e)[2]
            fingers["a" if cz < 10 else ("b" if cz < 22 else "c")].append(e)
    return segs, fingers

def build_arm(side, cs, sx):
    segs, fing = arm_split(cs)
    if sx < 0:
        segs = [[mirror(e) for e in sg] for sg in segs]
        fing = {k: [mirror(e) for e in v] for k, v in fing.items()}
    par = "tronco"
    for i in range(4):
        n = f"brazo_{side}{i+1}"
        bone(n, par, (sx * SEG[i], AY, AZ), segs[i]); par = n
    bone(f"mano_{side}", par, (sx * SEG[4], AY, AZ), []); hand = f"mano_{side}"
    for k, v in fing.items():
        bone(f"dedo_{side}_{k}", hand, (sx * SEG[4], AY, AZ), v)

build_arm("r", arm, 1)
build_arm("l", arm, -1)

# ----------------------------------------------------------------------------------------------
# Animaciones (DSL)
# ----------------------------------------------------------------------------------------------
class Anim:
    def __init__(s, name, length, loop=False, hold=False):
        s.name, s.length, s.loop, s.hold = name, length, loop, hold
        s.ch = {}   # bone -> channel -> list[(t, vec, interp)]
    def key(s, b, ch, t, v, interp="catmullrom"):
        s.ch.setdefault(b, {}).setdefault(ch, []).append((round(t, 4), list(v), interp))
    def rot(s, b, *kfs, interp="catmullrom"):
        for t, v in kfs: s.key(b, "rotation", t, v, interp)
    def pos(s, b, *kfs, interp="catmullrom"):
        for t, v in kfs: s.key(b, "position", t, v, interp)
    def scl(s, b, *kfs, interp="catmullrom"):
        for t, v in kfs: s.key(b, "scale", t, v, interp)
    def wave(s, b, ch, amp, period, phase=0.0, base=(0, 0, 0), step=0.5):
        """Seno periodico sobre el vector 'amp' (x,y,z). 'period' debe dividir la duracion."""
        n = int(round(s.length / step))
        for i in range(n + 1):
            t = min(s.length, i * s.length / n)
            k = math.sin(2 * math.pi * t / period + phase)
            s.key(b, ch, t, [base[j] + amp[j] * k for j in range(3)])
    def finish(s):
        for b in s.ch.values():
            for ch in b.values(): ch.sort(key=lambda a: a[0])
        return s

ANIMS = {}
def A(name, length, **kw):
    a = Anim(name, length, **kw); ANIMS[name] = a; return a

ARM_B = lambda side: [f"brazo_{side}{i}" for i in range(1, 5)] + [f"mano_{side}"]
FING = lambda side: [f"dedo_{side}_{k}" for k in "abc"]
PET = [f"petalo_{i}" for i in range(1, 9)]
TG = [f"lengua_{i}" for i in range(1, TG_N + 1)]
ROOTS = ["raices_n", "raices_s", "raices_e", "raices_w"]

def mir(side, v):
    """Pose escrita para el brazo DERECHO -> brazo izquierdo (espejo en X)."""
    return list(v) if side == "r" else [v[0], -v[1], -v[2]]

def arm_pose(a, side, t, shoulder_yaw, bends, hand=0.0, roll=0.0, curl=0.0, interp="catmullrom", sh_pitch=0.0):
    """bends: 3 angulos (r2,r3,r4) en el plano vertical del brazo (+ sube / - baja). Ver notas de ejes."""
    a.rot(f"brazo_{side}1", (t, mir(side, [roll, shoulder_yaw, sh_pitch])), interp=interp)
    for i, bnd in enumerate(bends):
        a.rot(f"brazo_{side}{i+2}", (t, mir(side, [roll * 0.3, 0, bnd])), interp=interp)
    a.rot(f"mano_{side}", (t, mir(side, [0, 0, hand])), interp=interp)
    for k, f in zip("abc", FING(side)):
        off = {"a": -8, "b": 0, "c": 8}[k]
        a.rot(f, (t, mir(side, [0, off * (1 + curl / 60), -curl])), interp=interp)

def tongue_pose(a, t, base_pitch, curls, yaw=0.0, scale=1.0, interp="catmullrom"):
    """base_pitch: giro del 1er segmento sobre su pose de reposo (-32). curls: lista de 7 angulos relativos."""
    a.rot("lengua_1", (t, [base_pitch, yaw, 0]), interp=interp)
    a.scl("lengua_1", (t, [scale, scale, scale]), interp=interp)
    for i in range(1, TG_N):
        a.rot(f"lengua_{i+1}", (t, [curls[min(i - 1, len(curls) - 1)], yaw * 0.2, 0]), interp=interp)

# ---- IDLE (8 s) -----------------------------------------------------------------------------
def idle(name, k_amp, k_speed):
    L = 8.0
    a = A(name, L, loop=True)
    p = lambda base: base / k_speed
    a.wave("tronco", "position", [0, 1.4 * k_amp, 0], p(4.0))
    a.wave("tronco", "scale", [0.012 * k_amp, 0.008 * k_amp, 0.012 * k_amp], p(4.0), base=(1, 1, 1))
    a.wave("tronco", "rotation", [0.8 * k_amp, 0.5 * k_amp, 0.9 * k_amp], p(8.0), 0.4)
    a.wave("cabeza", "rotation", [1.6 * k_amp, 3.0 * k_amp, 1.0 * k_amp], p(8.0), 1.1)
    a.wave("cabeza", "position", [0, 0.8 * k_amp, 0], p(4.0), 0.9)
    for i, b in enumerate(PET):
        a.wave(b, "rotation", [1.5 * k_amp, 0, 3.0 * k_amp * (1 if i % 2 else -1)], p(8.0 / (1 + i % 3)), i * 0.9)
    a.wave("tallo_1", "rotation", [1.5 * k_amp, 0, 3.5 * k_amp], p(8.0), 0.2)
    a.wave("tallo_2", "rotation", [2.0 * k_amp, 0, 7.0 * k_amp], p(8.0), 1.0)
    for i, b in enumerate(ROOTS):
        a.wave(b, "rotation", [1.4 * k_amp, 0, 1.4 * k_amp], p(4.0), i * 1.6)
    for side in "rl":
        s = 1 if side == "r" else -1
        for i, b in enumerate(ARM_B(side)):
            amp = [1.2, 3.0, 3.5, 4.0, 4.5][i] * k_amp
            ph = 0.6 * i + (0 if side == "r" else 1.7)
            a.wave(b, "rotation", [0.5 * amp, (2.0 * k_amp if i == 0 else 0) * s, amp * s * 0 + amp], p(8.0), ph)
        for j, f in enumerate(FING(side)):
            a.wave(f, "rotation", [0, 0, -5 * k_amp], p(4.0), j * 1.3 + (0 if side == "r" else 1.0), base=(0, 0, -6))
idle("idle", 1.0, 1.0)
idle("idle_fury", 2.1, 1.6)

# ---- TONGUE idle / fury ---------------------------------------------------------------------
def tongue_idle(name, amp, per):
    a = A(name, 4.0, loop=True)
    a.scl("lengua_1", (0, [0.26, 0.26, 0.26]), (2.0, [0.28, 0.28, 0.28]), (4.0, [0.26, 0.26, 0.26]))
    a.wave("lengua_1", "rotation", [3 * amp, 6 * amp, 0], per, 0.0, base=(10, 0, 0))
    for i in range(2, TG_N + 1):
        a.wave(f"lengua_{i}", "rotation", [-16 + 4 * amp * math.sin(i), 8 * amp, 0], per, i * 0.5, base=(-16, 0, 0))
    # nota: wave suma amp*sin a base, asi que el vector anterior se re-define abajo
    for i in range(2, TG_N + 1):
        a.ch[f"lengua_{i}"]["rotation"].clear()
        a.wave(f"lengua_{i}", "rotation", [4 * amp, 9 * amp, 0], per, i * 0.55, base=(-18, 0, 0))
tongue_idle("lengua_idle", 1.0, 4.0)
tongue_idle("lengua_idle_fury", 2.2, 2.0)

# ---- Tongue attack (3.2 s): anticipacion 0-1.0, latigazo 1.0-1.25, hold 1.25-1.9, retraccion 1.9-3.2
a = A("lengua_atacar", 3.2)
tongue_pose(a, 0.0, 10, [-18] * 7, scale=0.26)
tongue_pose(a, 0.35, 28, [-30, -26, -22, -18, -14, -10, -8], scale=0.34)          # se enrosca hacia atras
tongue_pose(a, 0.8, 46, [-44, -34, -26, -20, -16, -12, -10], scale=0.40)
tongue_pose(a, 1.0, 50, [-52, -40, -30, -22, -16, -12, -8], scale=0.42)           # carga maxima
tongue_pose(a, 1.12, 14, [14, 10, 8, 6, 4, 2, 0], scale=0.85)                      # latigazo (ola)
tongue_pose(a, 1.25, -6, [0, 0, 0, 0, 0, 0, 0], scale=1.0)                         # extendida y apuntando al suelo (impacto)
tongue_pose(a, 1.6, -6, [2, -2, 3, -2, 2, -1, 0], scale=1.0)
tongue_pose(a, 1.9, -5, [0, 0, 0, 0, 0, 0, 0], scale=0.98)
tongue_pose(a, 2.3, 24, [-20, -14, -12, -10, -8, -8, -6], scale=0.62)              # retraccion
tongue_pose(a, 2.8, 14, [-18, -14, -16, -16, -16, -16, -14], scale=0.33)
tongue_pose(a, 3.2, 10, [-18] * 7, scale=0.26)

# ---- Tongue roar / death
a = A("lengua_rugir", 3.0)
tongue_pose(a, 0.0, 10, [-18] * 7, scale=0.26)
tongue_pose(a, 0.6, 40, [-10, -8, -6, -4, -4, -2, 0], scale=0.55)
tongue_pose(a, 1.2, 20, [6, 10, 6, 10, 6, 10, 6], scale=0.95, yaw=10)
tongue_pose(a, 1.8, 20, [-6, -10, -6, -10, -6, -10, -6], scale=0.95, yaw=-10)
tongue_pose(a, 2.4, 20, [6, 8, 6, 8, 6, 8, 6], scale=0.9, yaw=6)
tongue_pose(a, 3.0, 10, [-18] * 7, scale=0.26)

a = A("lengua_morir", 5.0, hold=True)
tongue_pose(a, 0.0, 10, [-18] * 7, scale=0.26)
tongue_pose(a, 1.0, 30, [-4, -2, 0, 0, 0, 0, 0], scale=0.8)
tongue_pose(a, 2.4, 70, [-6, -6, -8, -10, -10, -10, -10], scale=1.0)
tongue_pose(a, 5.0, 80, [-8, -8, -8, -8, -8, -8, -8], scale=1.0)

# ---- SPAWN (10 s) ---------------------------------------------------------------------------
a = A("spawn", 10.0, hold=True)
a.pos("raiz", (0, [0, -340, 0]), (3.5, [0, -340, 0]), (4.5, [0, -300, 0]), (6.0, [0, -170, 0]), (7.4, [0, -40, 0]), (8.0, [0, 0, 0]),
      (8.25, [0, -10, 0]), (8.6, [0, 0, 0]), (10.0, [0, 0, 0]))
# temblor subterraneo
for i in range(0, 36):
    t = i * 0.1
    if t < 7.4:
        amp = 2.5 if t < 3.5 else 5.0
        a.key("raiz", "position", t + 0.05, [math.sin(i * 7.1) * amp * 0.4, -340 + 0 if t < 3.5 else 0, math.cos(i * 5.3) * amp * 0.4], "linear") if False else None
for side in "rl":
    # brazos plegados hacia abajo -> despliegue -> golpe contra el suelo (8.0) -> alzados en rugido
    arm_pose(a, side, 0.0, 10, [-60, -50, -40], hand=-30, curl=40)
    arm_pose(a, side, 5.0, 12, [-62, -50, -40], hand=-30, curl=40)
    arm_pose(a, side, 6.2, 30, [-30, -20, -10], hand=-10, curl=20)
    arm_pose(a, side, 7.2, 60, [18, 22, 18], hand=10, curl=10)                      # se alza
    arm_pose(a, side, 7.95, 88, [-14, -14, -12], hand=-8, curl=0)                   # golpe presentacion
    arm_pose(a, side, 8.4, 84, [-12, -12, -10], hand=-6, curl=0)
    arm_pose(a, side, 9.0, 30, [24, 26, 22], hand=14, curl=30)                      # alzados (rugido)
    arm_pose(a, side, 10.0, 24, [18, 20, 16], hand=10, curl=25)
a.rot("cabeza", (0, [30, 0, 0]), (5.0, [28, 4, 0]), (7.0, [10, -4, 0]), (8.0, [-6, 0, 0]), (8.9, [32, 0, 0]), (9.4, [34, 0, 4]), (10.0, [20, 0, 0]))
a.rot("tronco", (0, [0, 0, 0]), (6.0, [4, 0, -2]), (8.0, [-6, 0, 2]), (8.9, [8, 0, 0]), (10.0, [2, 0, 0]))
a.scl("tronco", (0, [1, 1, 1]), (8.6, [1, 1, 1]), (9.2, [1.05, 1.04, 1.05]), (10.0, [1, 1, 1]))
for i, b in enumerate(PET):
    sgn = 1 if i % 2 else -1
    a.rot(b, (0, [-30, 0, 20 * sgn]), (6.5, [-26, 0, 18 * sgn]), (8.0, [10, 0, -6 * sgn]), (8.9, [-14, 0, 22 * sgn]), (10.0, [-4, 0, 6 * sgn]))
for i, b in enumerate(ROOTS):
    a.rot(b, (0, [12, 0, 0]), (7.0, [-8, 0, 0]), (8.0, [10, 0, 0]), (10.0, [0, 0, 0]))
a.rot("tallo_1", (0, [-40, 0, 0]), (7.0, [-30, 0, 4]), (8.2, [10, 0, -5]), (10.0, [0, 0, 0]))
a.rot("tallo_2", (0, [-60, 0, 0]), (7.5, [-40, 0, 8]), (8.4, [18, 0, -10]), (10.0, [0, 0, 0]))

# ---- SLAM (brazo aplastante): total 2.6 s, impacto a 1.45 s -------------------------------------
def slam(side):
    a = A(f"slam_{side}", 2.6)
    o = "l" if side == "r" else "r"
    arm_pose(a, side, 0.0, 0, [0, 0, 0])
    arm_pose(a, side, 0.3, -12, [-8, -8, -6], hand=-4, curl=20, roll=6)             # anticipacion: se recoge
    arm_pose(a, side, 0.9, 46, [26, 28, 24], hand=16, curl=35, roll=-4)             # alza
    arm_pose(a, side, 1.3, 62, [34, 34, 30], hand=22, curl=45, roll=-6)             # tope
    arm_pose(a, side, 1.45, 90, [-14, -14, -12], hand=-8, curl=0, roll=0, interp="linear")   # IMPACTO
    arm_pose(a, side, 1.6, 88, [-12, -12, -10], hand=-6, curl=0)                    # rebote
    arm_pose(a, side, 1.75, 90, [-14, -14, -12], hand=-8, curl=0)
    arm_pose(a, side, 2.2, 40, [8, 10, 8], hand=4, curl=12)
    arm_pose(a, side, 2.6, 0, [0, 0, 0])
    a.pos("tronco", (0, [0, 0, 0]), (1.2, [0, 3, 0]), (1.45, [0, -6, -4]), (1.7, [0, -2, -1]), (2.6, [0, 0, 0]))
    a.rot("tronco", (0, [0, 0, 0]), (0.9, [-4, -8 if side == "r" else 8, 0]), (1.3, [-6, -10 if side == "r" else 10, 0]),
          (1.45, [9, 6 if side == "r" else -6, 0]), (1.9, [3, 0, 0]), (2.6, [0, 0, 0]))
    a.rot("cabeza", (0, [0, 0, 0]), (1.0, [-8, 0, 0]), (1.45, [14, 0, 0]), (2.0, [4, 0, 0]), (2.6, [0, 0, 0]))
    for i, b in enumerate(PET):
        a.rot(b, (0, [0, 0, 0]), (1.3, [-6, 0, 8 * (1 if i % 2 else -1)]), (1.5, [10, 0, -6 * (1 if i % 2 else -1)]), (2.6, [0, 0, 0]))
    for b in ROOTS:
        a.rot(b, (0, [0, 0, 0]), (1.45, [-8, 0, 0]), (1.7, [5, 0, 0]), (2.6, [0, 0, 0]))
    # el brazo contrario se apoya (contrapeso)
    arm_pose(a, o, 0.0, 0, [0, 0, 0]); arm_pose(a, o, 1.3, -6, [-4, -2, 0], curl=10); arm_pose(a, o, 1.5, -4, [-6, -4, -2], curl=14)
    arm_pose(a, o, 2.6, 0, [0, 0, 0])
    return a
slam("r"); slam("l")

# ---- SWEEP (ataque arrastrado): total 3.4 s, arrastre 1.0 -> 2.0 s, yaw -15 -> 150 -------------------
SW_PSI0, SW_PSI1 = -15, 150
def sweep(side):
    a = A(f"sweep_{side}", 3.4)
    o = "l" if side == "r" else "r"
    arm_pose(a, side, 0.0, 0, [0, 0, 0])
    arm_pose(a, side, 0.25, -6, [-4, -4, -2], curl=14)
    arm_pose(a, side, 0.65, SW_PSI0 - 16, [16, 14, 10], hand=8, curl=25, roll=-8)   # se levanta ligeramente y se echa atras
    arm_pose(a, side, 1.0, SW_PSI0, [-14, -14, -12], hand=-8, curl=10)              # baja y apoya
    # arrastre: yaw continuo y suave, segmentos con retardo (efecto latigo organico)
    for i, (t, psi) in enumerate([(1.0, SW_PSI0), (1.25, 8), (1.5, 62), (1.75, 118), (2.0, SW_PSI1)]):
        a.rot(f"brazo_{side}1", (t, mir(side, [0, psi, 0])), interp="catmullrom")
    for j in range(2, 5):
        lag = (j - 1) * 0.06
        for t, bend in [(1.0, -14), (1.25 + lag, -17), (1.6 + lag, -15), (2.0 + lag, -13)]:
            a.rot(f"brazo_{side}{j}", (t, mir(side, [0, 0, bend])))
        # pequena curvatura lateral por arrastre (el brazo se retrasa respecto a la direccion del movimiento)
        for t, lat in [(1.0, 0), (1.3, -9), (1.7, -11), (2.0, -4), (2.35, 2)]:
            pass
    a.rot("mano_" + side, (1.0, mir(side, [0, 0, -8])), (1.5, mir(side, [0, 0, -9])), (2.0, mir(side, [0, 0, -6])))
    for f in FING(side): a.rot(f, (1.0, mir(side, [0, 0, -10])), (1.6, mir(side, [0, 0, -22])), (2.0, mir(side, [0, 0, -12])))
    arm_pose(a, side, 2.2, SW_PSI1 + 4, [-12, -12, -10], hand=-6, curl=8)
    arm_pose(a, side, 2.7, 70, [10, 10, 8], hand=4, curl=14)
    arm_pose(a, side, 3.4, 0, [0, 0, 0])
    sg = 1 if side == "r" else -1
    a.rot("tronco", (0, [0, 0, 0]), (0.65, [-3, -9 * sg, 0]), (1.0, [2, -10 * sg, 0]), (1.5, [3, 2 * sg, 0]),
          (2.0, [2, 14 * sg, 0]), (2.6, [0, 6 * sg, 0]), (3.4, [0, 0, 0]))
    a.pos("tronco", (0, [0, 0, 0]), (1.0, [0, -4, 0]), (2.0, [0, -3, 0]), (3.4, [0, 0, 0]))
    a.rot("cabeza", (0, [0, 0, 0]), (1.0, [4, -10 * sg, 0]), (2.0, [4, 16 * sg, 0]), (3.4, [0, 0, 0]))
    for i, b in enumerate(PET):
        a.rot(b, (0, [0, 0, 0]), (1.5, [0, 0, 7 * (1 if i % 2 else -1)]), (2.2, [0, 0, -5 * (1 if i % 2 else -1)]), (3.4, [0, 0, 0]))
    arm_pose(a, o, 0.0, 0, [0, 0, 0]); arm_pose(a, o, 1.2, -5, [-3, -3, -2], curl=8); arm_pose(a, o, 2.2, -5, [-6, -3, -2], curl=10)
    arm_pose(a, o, 3.4, 0, [0, 0, 0])
    return a
sweep("r"); sweep("l")

# ---- GRAB (agarre): total 2.4 s: el brazo atrapa y estruja, tras la lengua ---------------------------
def grab(side):
    a = A(f"grab_{side}", 2.4)
    arm_pose(a, side, 0.0, 0, [0, 0, 0])
    arm_pose(a, side, 0.4, 40, [20, 14, 10], hand=10, curl=-20, roll=0)             # dedos abiertos
    arm_pose(a, side, 0.8, 84, [4, 2, -2], hand=0, curl=-30)                        # alcanza al frente
    arm_pose(a, side, 1.0, 88, [-6, -6, -4], hand=-4, curl=70, interp="linear")     # cierra el punio
    arm_pose(a, side, 1.4, 86, [-4, -4, -2], hand=-2, curl=78)                      # estruja
    arm_pose(a, side, 1.8, 70, [12, 14, 10], hand=6, curl=40)                       # lanza
    arm_pose(a, side, 2.4, 0, [0, 0, 0])
    a.rot("tronco", (0, [0, 0, 0]), (0.8, [-4, -6 if side == "r" else 6, 0]), (1.2, [5, 0, 0]), (2.4, [0, 0, 0]))
    return a
grab("r"); grab("l")

# ---- ROOTS cast (invoca raices): 2.4 s ---------------------------------------------------------------
a = A("roots_cast", 2.4)
for side in "rl":
    arm_pose(a, side, 0.0, 0, [0, 0, 0])
    arm_pose(a, side, 0.5, 6, [-30, -26, -20], hand=-20, curl=25)
    arm_pose(a, side, 1.0, 22, [-60, -52, -40], hand=-30, curl=45)                 # hincan los brazos hacia la tierra
    arm_pose(a, side, 1.3, 40, [-52, -44, -34], hand=-20, curl=30, interp="linear") # clavan
    arm_pose(a, side, 1.7, 36, [-44, -38, -30], hand=-16, curl=26)
    arm_pose(a, side, 2.4, 0, [0, 0, 0])
a.pos("tronco", (0, [0, 0, 0]), (1.0, [0, -5, 0]), (1.3, [0, -9, 0]), (2.4, [0, 0, 0]))
a.rot("cabeza", (0, [0, 0, 0]), (1.0, [10, 0, 0]), (1.3, [20, 0, 0]), (2.4, [0, 0, 0]))
for i, b in enumerate(ROOTS):
    a.rot(b, (0, [0, 0, 0]), (0.9, [-6, 0, 0]), (1.3, [10, 0, 0]), (2.0, [-4, 0, 0]), (2.4, [0, 0, 0]))

# ---- GARDEN cast (jardin maldito): 3.0 s -------------------------------------------------------------
a = A("garden_cast", 3.0)
for side in "rl":
    arm_pose(a, side, 0.0, 0, [0, 0, 0])
    arm_pose(a, side, 0.8, 10, [24, 26, 20], hand=14, curl=30)
    arm_pose(a, side, 1.5, 4, [46, 40, 34], hand=24, curl=-20)                     # abre los brazos al cielo
    arm_pose(a, side, 2.1, 6, [44, 38, 32], hand=22, curl=-10)
    arm_pose(a, side, 3.0, 0, [0, 0, 0])
a.rot("cabeza", (0, [0, 0, 0]), (1.0, [-10, 0, 0]), (1.5, [30, 0, 0]), (2.2, [24, 0, 0]), (3.0, [0, 0, 0]))
a.rot("tronco", (0, [0, 0, 0]), (1.5, [-8, 0, 0]), (2.2, [-6, 0, 0]), (3.0, [0, 0, 0]))
for i, b in enumerate(PET):
    s = 1 if i % 2 else -1
    a.rot(b, (0, [0, 0, 0]), (1.0, [8, 0, 10 * s]), (1.5, [18, 0, 26 * s]), (2.3, [14, 0, 20 * s]), (3.0, [0, 0, 0]))
for b in ["tallo_1", "tallo_2"]:
    a.rot(b, (0, [0, 0, 0]), (1.5, [-14, 0, 5]), (2.3, [10, 0, -6]), (3.0, [0, 0, 0]))
for b in ROOTS:
    a.rot(b, (0, [0, 0, 0]), (1.5, [-12, 0, 0]), (2.3, [8, 0, 0]), (3.0, [0, 0, 0]))

# ---- VINE cast (enredadera cazadora): 2.6 s: el tallo superior se arquea y lanza la enredadera ------------
a = A("vine_cast", 2.6)
for side in "rl":
    arm_pose(a, side, 0.0, 0, [0, 0, 0])
    arm_pose(a, side, 1.0, 10, [10, 10, 8], hand=6, curl=20)
    arm_pose(a, side, 1.6, 4, [-6, -6, -4], hand=-4, curl=10)
    arm_pose(a, side, 2.6, 0, [0, 0, 0])
a.rot("tallo_1", (0, [0, 0, 0]), (0.5, [-18, 0, 6]), (1.0, [-34, 0, 12]), (1.3, [-38, 0, 14]), (1.5, [30, 0, 0], ), (1.8, [14, 0, -4]), (2.6, [0, 0, 0]))
a.rot("tallo_2", (0, [0, 0, 0]), (0.5, [-30, 0, 10]), (1.0, [-60, 0, 20]), (1.3, [-70, 0, 24]), (1.5, [46, 0, -10]), (1.8, [20, 0, 6]), (2.6, [0, 0, 0]))
a.rot("cabeza", (0, [0, 0, 0]), (1.0, [-12, 0, 0]), (1.5, [16, 0, 0]), (2.6, [0, 0, 0]))
for i, b in enumerate(PET):
    s = 1 if i % 2 else -1
    a.rot(b, (0, [0, 0, 0]), (1.0, [0, 0, 14 * s]), (1.5, [0, 0, -10 * s]), (2.6, [0, 0, 0]))

# ---- HURT / STUN / FURY / DEATH ------------------------------------------------------------------------
a = A("hurt", 0.6)
a.rot("tronco", (0, [0, 0, 0]), (0.12, [-7, 0, 3]), (0.35, [2, 0, -1]), (0.6, [0, 0, 0]))
a.rot("cabeza", (0, [0, 0, 0]), (0.12, [-14, 4, 0]), (0.35, [4, 0, 0]), (0.6, [0, 0, 0]))
for i, b in enumerate(PET):
    a.rot(b, (0, [0, 0, 0]), (0.12, [-10, 0, 8 * (1 if i % 2 else -1)]), (0.6, [0, 0, 0]))

a = A("stun", 3.0, loop=True)
for side in "rl":
    arm_pose(a, side, 0.0, 6, [-24, -22, -18], hand=-10, curl=30)
    arm_pose(a, side, 1.5, 8, [-30, -26, -20], hand=-14, curl=36)
    arm_pose(a, side, 3.0, 6, [-24, -22, -18], hand=-10, curl=30)
a.wave("cabeza", "rotation", [6, 8, 6], 1.5, 0.3, base=(34, 0, 0), step=0.25)
a.wave("tronco", "rotation", [2, 2, 3], 1.0, 0.0, base=(10, 0, 0), step=0.25)
a.wave("tronco", "position", [0, 0.6, 0], 1.0, 0.0, base=(0, -8, 0), step=0.25)
for i, b in enumerate(PET): a.wave(b, "rotation", [4, 0, 8 * (1 if i % 2 else -1)], 1.0, i * 0.7, base=(-16, 0, 0), step=0.25)
for b in ROOTS: a.wave(b, "rotation", [3, 0, 3], 1.0, 1.0, step=0.25)

a = A("fury", 3.0)
for side in "rl":
    arm_pose(a, side, 0.0, 0, [0, 0, 0])
    arm_pose(a, side, 0.6, 20, [-26, -22, -16], hand=-12, curl=40)
    arm_pose(a, side, 1.2, 30, [50, 44, 36], hand=26, curl=-26)                     # se alzan en rugido
    arm_pose(a, side, 1.55, 86, [-14, -14, -12], hand=-8, curl=60, interp="linear") # golpean el suelo
    arm_pose(a, side, 2.1, 40, [22, 24, 18], hand=12, curl=40)
    arm_pose(a, side, 3.0, 0, [0, 0, 0])
a.rot("cabeza", (0, [0, 0, 0]), (0.6, [-14, 0, 0]), (1.2, [38, 0, 0]), (1.55, [8, 0, 0]), (2.2, [30, 0, 0]), (3.0, [0, 0, 0]))
a.rot("tronco", (0, [0, 0, 0]), (0.6, [-8, 0, 0]), (1.2, [10, 0, 0]), (1.55, [-10, 0, 0]), (3.0, [0, 0, 0]))
a.pos("tronco", (0, [0, 0, 0]), (0.6, [0, -6, 0]), (1.2, [0, 8, 0]), (1.55, [0, -10, 0]), (3.0, [0, 0, 0]))
for i, b in enumerate(PET):
    s = 1 if i % 2 else -1
    a.rot(b, (0, [0, 0, 0]), (0.6, [-18, 0, 10 * s]), (1.2, [22, 0, 34 * s]), (1.55, [-8, 0, -12 * s]), (2.4, [10, 0, 14 * s]), (3.0, [0, 0, 0]))
for b in ["tallo_1", "tallo_2"]:
    a.rot(b, (0, [0, 0, 0]), (0.6, [-16, 0, 6]), (1.2, [22, 0, -10]), (1.55, [-12, 0, 10]), (3.0, [0, 0, 0]))
for b in ROOTS:
    a.rot(b, (0, [0, 0, 0]), (1.2, [-18, 0, 0]), (1.55, [14, 0, 0]), (3.0, [0, 0, 0]))

a = A("death", 5.0, hold=True)
for side in "rl":
    arm_pose(a, side, 0.0, 0, [0, 0, 0])
    arm_pose(a, side, 0.6, 20, [30, 26, 20], hand=14, curl=-20)
    arm_pose(a, side, 1.4, 14, [-10, -8, -6], hand=-6, curl=10)
    arm_pose(a, side, 3.0, 8, [-40, -36, -30], hand=-20, curl=40)
    arm_pose(a, side, 5.0, 4, [-70, -60, -50], hand=-30, curl=50)
a.rot("cabeza", (0, [0, 0, 0]), (0.6, [-20, 0, 0]), (1.4, [20, 0, 0]), (3.0, [46, 0, 5]), (5.0, [58, 0, 6]))
a.rot("tronco", (0, [0, 0, 0]), (0.8, [-8, 0, 0]), (2.0, [8, 0, 2]), (5.0, [14, 0, 0]))
a.pos("raiz", (0, [0, 0, 0]), (1.6, [0, -3, 0]), (3.0, [0, -60, 0]), (5.0, [0, -330, 0]))
for i, b in enumerate(PET):
    s = 1 if i % 2 else -1
    a.rot(b, (0, [0, 0, 0]), (0.8, [-12, 0, 18 * s]), (2.5, [26, 0, 30 * s]), (5.0, [48, 0, 42 * s]))
for b in ["tallo_1", "tallo_2"]:
    a.rot(b, (0, [0, 0, 0]), (1.5, [14, 0, 4]), (5.0, [60, 0, 10]))
for b in ROOTS:
    a.rot(b, (0, [0, 0, 0]), (1.0, [-14, 0, 0]), (3.0, [10, 0, 0]), (5.0, [30, 0, 0]))

for an in ANIMS.values(): an.finish()

# ----------------------------------------------------------------------------------------------
# Exportadores
# ----------------------------------------------------------------------------------------------
palette = list(range(0, 8))

def bb_group(name):
    b = bones[name]
    return {"name": name, "origin": b["pivot"], "rotation": b["rot"], "color": palette[hash(name) % 8], "uuid": guid[name],
            "export": True, "mirror_uv": False, "isOpen": False, "locked": False, "visibility": True, "autouv": 0,
            "children": []}
guid = {n: U() for n in order}
def outliner(parent):
    res = []
    for n in order:
        if bones[n]["parent"] == parent:
            g = bb_group(n)
            g["children"] = outliner(n) + [e["uuid"] for e in bones[n]["cubes"]]
            res.append(g)
    return res
all_elements = []
for n in order: all_elements += bones[n]["cubes"]

def bb_anim(an):
    animators = {}
    for b, chs in an.ch.items():
        kfs = []
        for ch, lst in chs.items():
            for t, v, interp in lst:
                kfs.append({"channel": ch, "data_points": [{"x": str(round(v[0], 4)), "y": str(round(v[1], 4)), "z": str(round(v[2], 4))}],
                            "uuid": U(), "time": t, "color": -1, "interpolation": interp})
        animators[guid[b]] = {"name": b, "type": "bone", "keyframes": kfs}
    return {"uuid": U(), "name": f"animation.qumara.{an.name}", "loop": "loop" if an.loop else ("hold" if an.hold else "once"),
            "override": False, "length": an.length, "snapping": 20, "selected": False, "anim_time_update": "", "blend_weight": "",
            "start_delay": "", "loop_delay": "", "animators": animators}

bb = {k: v for k, v in d.items() if k not in ("groups", "outliner", "elements", "animations")}
bb["name"] = "qumara.geo"; bb["model_identifier"] = "qumara"
bb["elements"] = all_elements
bb["outliner"] = outliner(None)
bb["animations"] = [bb_anim(a) for a in ANIMS.values()]
os.makedirs(os.path.dirname(OUT_BB), exist_ok=True)
json.dump(bb, open(OUT_BB, "w"), indent=1)

# ---- geo.json (Bedrock 1.12.0, convencion Blockbench: X invertida) --------------------------------------------
def r3(v): return [round(x, 4) for x in v]
def geo_cube(e):
    f, t = e["from"], e["to"]
    c = {"origin": r3([-t[0], f[1], f[2]]), "size": r3([t[0] - f[0], t[1] - f[1], t[2] - f[2]])}
    if e.get("rotation") and any(abs(x) > 1e-6 for x in e["rotation"]):
        o = e.get("origin", [0, 0, 0]); r = e["rotation"]
        c["pivot"] = r3([-o[0], o[1], o[2]]); c["rotation"] = r3([r[0], -r[1], -r[2]])
    uv = {}
    for k, v in e["faces"].items():
        if v.get("texture") is None: continue
        u = v["uv"]; kk = {"east": "west", "west": "east"}.get(k, k)
        uv[kk] = {"uv": [u[0], u[1]], "uv_size": [round(u[2] - u[0], 4), round(u[3] - u[1], 4)]}
    c["uv"] = uv
    return c
geo_bones = []
for n in order:
    b = bones[n]
    gb = {"name": n, "pivot": r3([-b["pivot"][0], b["pivot"][1], b["pivot"][2]])}
    if b["parent"]: gb["parent"] = b["parent"]
    if any(abs(x) > 1e-6 for x in b["rot"]): gb["rotation"] = r3([b["rot"][0], -b["rot"][1], -b["rot"][2]])
    if b["cubes"]: gb["cubes"] = [geo_cube(e) for e in b["cubes"]]
    geo_bones.append(gb)
geo = {"format_version": "1.12.0", "minecraft:geometry": [{
    "description": {"identifier": "geometry.qumara", "texture_width": 512, "texture_height": 512,
                    "visible_bounds_width": 40, "visible_bounds_height": 32, "visible_bounds_offset": [0, 8, 0]},
    "bones": geo_bones}]}
os.makedirs(os.path.dirname(OUT_GEO), exist_ok=True)
json.dump(geo, open(OUT_GEO, "w"), indent=1)

# ---- animation.json -------------------------------------------------------------------------------------------
def conv(ch, v):
    s = ROT_SIGN if ch == "rotation" else (POS_SIGN if ch == "position" else (1, 1, 1))
    return [round(v[i] * s[i], 4) for i in range(3)]
def anim_json(an):
    bones_j = {}
    for b, chs in an.ch.items():
        bj = {}
        for ch, lst in chs.items():
            kj = {}
            for t, v, interp in lst:
                val = conv(ch, v)
                kj[str(t)] = {"post": val, "lerp_mode": "catmullrom"} if interp == "catmullrom" else val
            bj[ch] = kj
        bones_j[b] = bj
    out = {"animation_length": an.length, "bones": bones_j}
    out["loop"] = True if an.loop else ("hold_on_last_frame" if an.hold else False)
    return out
anims_j = {"format_version": "1.8.0", "animations": {f"animation.qumara.{n}": anim_json(a) for n, a in ANIMS.items()}}
os.makedirs(os.path.dirname(OUT_ANIM), exist_ok=True)
json.dump(anims_j, open(OUT_ANIM, "w"), indent=1)

print("huesos:", len(order), "cubos:", len(all_elements), "animaciones:", len(ANIMS))
print("\n".join(f"  {n:<14} len={a.length:<4} bones={len(a.ch)}" for n, a in ANIMS.items()))

if "--fk" in sys.argv:
    # Comprobacion cinematica aproximada de las poses clave (en bloques, escala del render 0.5)
    import numpy as np
    def Rm(r):
        rx, ry, rz = [math.radians(v) for v in r]
        Rx = np.array([[1, 0, 0], [0, math.cos(rx), -math.sin(rx)], [0, math.sin(rx), math.cos(rx)]])
        Ry = np.array([[math.cos(ry), 0, math.sin(ry)], [0, 1, 0], [-math.sin(ry), 0, math.cos(ry)]])
        Rz = np.array([[math.cos(rz), -math.sin(rz), 0], [math.sin(rz), math.cos(rz), 0], [0, 0, 1]])
        return Rz @ Ry @ Rx
    def tip(an, t, side):
        def val(b):
            lst = an.ch.get(b, {}).get("rotation", [])
            if not lst: return [0, 0, 0]
            for i in range(len(lst) - 1):
                if lst[i][0] <= t <= lst[i + 1][0]:
                    k = (t - lst[i][0]) / max(1e-6, lst[i + 1][0] - lst[i][0])
                    return [lst[i][1][j] * (1 - k) + lst[i + 1][1][j] * k for j in range(3)]
            return lst[-1][1] if t > lst[-1][0] else lst[0][1]
        p = np.array([SEG[4] + 69.0, AY, AZ]) * np.array([1 if side == "r" else -1, 1, 1])
        for b in ["mano_" + side] + [f"brazo_{side}{i}" for i in (4, 3, 2, 1)]:
            pv = np.array(bones[b]["pivot"]); p = Rm(val(b)) @ (p - pv) + pv
        return p * 0.5 / 16
    for nm, t in [("slam_r", 0.0), ("slam_r", 1.3), ("slam_r", 1.45), ("sweep_r", 1.0), ("sweep_r", 1.5), ("sweep_r", 2.0), ("grab_r", 1.0)]:
        p = tip(ANIMS[nm], t, "r"); print(f"  FK {nm}@{t}: punta mano (bloques) x={p[0]:.2f} y={p[1]:.2f} z={p[2]:.2f}  (frente = -z)")
