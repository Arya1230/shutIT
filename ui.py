"""
ui.py - shutIT — Glassmorphism dark, smooth circle icon, pulse ring, animated toggle.
"""

import os, sys, threading, ctypes
from ctypes import windll, c_int, byref, sizeof, Structure, POINTER as CPTR
import tkinter as tk
import tkinter.font as tkfont
from PIL import Image, ImageTk, ImageDraw, ImageFilter
import pystray
import mic_logic

# ── Resource path ─────────────────────────────────────────────────────────────
def _res(*p):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *p)

# ── Windows DWM Acrylic (glassmorphism) ───────────────────────────────────────
class _ACCENT(Structure):
    _fields_ = [("AccentState",c_int),("AccentFlags",c_int),
                 ("GradientColor",c_int),("AnimationId",c_int)]
class _WCA(Structure):
    _fields_ = [("Attribute",c_int),("Data",CPTR(_ACCENT)),("SizeOfData",ctypes.c_size_t)]

def _apply_acrylic(hwnd):
    try:
        # ABGR tint: alpha=0x88, very dark — more blur, less tint
        accent = _ACCENT(4, 2, 0x880d0d0d, 0)
        data   = _WCA(19, ctypes.pointer(accent), sizeof(accent))
        windll.user32.SetWindowCompositionAttribute(hwnd, byref(data))
    except Exception:
        pass

# ── Palette ───────────────────────────────────────────────────────────────────
BG        = "#0d0d0d"
CARD      = "#181818"
CARD_HOV  = "#202020"
BORDER    = "#2e2e2e"
BORDER_HI = "#404040"
TEXT_PRI  = "#ffffff"
TEXT_SEC  = "#aaaaaa"
TEXT_DIM  = "#666666"

LIVE_HI   = "#22c55e"
LIVE_MID  = "#16a34a"
MUTED_HI  = "#ef4444"
MUTED_MID = "#dc2626"

TW, TH    = 48, 26

# ── Helpers ───────────────────────────────────────────────────────────────────
def _rr(cv, x1, y1, x2, y2, r, **kw):
    pts = [x1+r,y1,x2-r,y1,x2,y1,x2,y1+r,x2,y2-r,x2,y2,
           x2-r,y2,x1+r,y2,x1,y2,x1,y2-r,x1,y1+r,x1,y1,x1+r,y1]
    cv.create_polygon(pts, smooth=True, **kw)

def _lerp(c1, c2, t):
    t = max(0.0, min(1.0, t))
    r = int(int(c1[1:3],16)+(int(c2[1:3],16)-int(c1[1:3],16))*t)
    g = int(int(c1[3:5],16)+(int(c2[3:5],16)-int(c1[3:5],16))*t)
    b = int(int(c1[5:7],16)+(int(c2[5:7],16)-int(c1[5:7],16))*t)
    return f"#{r:02x}{g:02x}{b:02x}"

def _tray_img(muted):
    c = (239,68,68,255) if muted else (34,197,94,255)
    b = Image.new("RGBA",(64,64),(0,0,0,0))
    ImageDraw.Draw(b).ellipse((0,0,63,63), fill=c)
    try:
        ic = Image.open(_res("icons","micophone_mute.png" if muted else "microphone.png")
                        ).convert("RGBA").resize((44,44),Image.LANCZOS)
        b.paste(ic,(10,10),ic)
    except Exception: pass
    return b

# ── Smooth circle icon (2× supersampling, no pixelation) ─────────────────────
def _make_circle_img(muted: bool, size: int) -> Image.Image:
    """Render a crisp anti-aliased circle with the mic icon at 2× then downsample."""
    S = size * 2                          # 2× supersampling
    img  = Image.new("RGBA", (S, S), (0,0,0,0))
    draw = ImageDraw.Draw(img)

    color = (239,68,68,255) if muted else (34,197,94,255)
    draw.ellipse((2, 2, S-3, S-3), fill=color)

    try:
        ic_size = int(S * 0.60)
        pad     = (S - ic_size) // 2
        ic = Image.open(
            _res("icons","micophone_mute.png" if muted else "microphone.png")
        ).convert("RGBA").resize((ic_size, ic_size), Image.LANCZOS)
        img.paste(ic, (pad, pad), ic)
    except Exception:
        pass

    return img.resize((size, size), Image.LANCZOS)   # downsample → smooth


# ── Animated toggle ───────────────────────────────────────────────────────────
class ToggleSwitch(tk.Canvas):
    def __init__(self, parent, var, command=None, bg=BG, **kw):
        super().__init__(parent, width=TW, height=TH, bg=bg, highlightthickness=0, **kw)
        self._var, self._cmd = var, command
        self._x   = float(self._tgt())
        self._aid = None
        self._draw(self._x)
        var.trace_add("write", lambda *_: self._anim())
        self.bind("<Button-1>", self._click)

    def _tgt(self): return TW - TH//2 - 2 if self._var.get() else TH//2 + 2

    def _draw(self, x):
        self.delete("all")
        t     = max(0, min(1,(x-(TH//2+2))/(TW-TH-2)))
        track = _lerp(BORDER, TEXT_PRI, t)
        knob  = _lerp("#4a4a4a", BG, t)
        _rr(self,1,1,TW-1,TH-1,TH//2,fill=track,outline="")
        r = TH//2 - 3
        self.create_oval(x-r,TH//2-r,x+r,TH//2+r,fill=knob,outline="")

    def _anim(self):
        if self._aid: self.after_cancel(self._aid)
        s0, s1, N = self._x, float(self._tgt()), 10
        def tick(n):
            self._x = s1 + (s0-s1)*((N-n)/N)**1.8
            self._draw(self._x)
            if n < N: self._aid = self.after(14, tick, n+1)
            else:     self._x = s1; self._draw(s1)
        tick(1)

    def _click(self,_):
        self._var.set(not self._var.get())
        if self._cmd: self._cmd()


# ── Icon button: pure circle + pulse ring ─────────────────────────────────────
class IconButton(tk.Canvas):
    PAD = 16   # extra canvas padding around circle for pulse ring

    def __init__(self, parent, muted: bool, command=None, circle=110, **kw):
        size = circle + self.PAD * 2
        super().__init__(parent, width=size, height=size,
                         bg=BG, highlightthickness=0, **kw)
        self._c    = circle           # circle diameter
        self._s    = size
        self._muted= muted
        self._cmd  = command
        self._hover= False
        self._ref  = None
        self._draw()
        self.bind("<Button-1>", lambda _: self._cmd and self._cmd())
        self.bind("<Enter>",    lambda _: self._set_hover(True))
        self.bind("<Leave>",    lambda _: self._set_hover(False))

    def _draw(self):
        self.delete("main")
        s, c, pad = self._s, self._c, self.PAD
        # Render crisp circle image at actual circle size
        sz = c - (4 if self._hover else 0)   # slight shrink on hover
        img = _make_circle_img(self._muted, sz)
        self._ref = ImageTk.PhotoImage(img)
        self.create_image(s//2, s//2, image=self._ref, anchor="center", tags="main")

    def _set_hover(self, v):
        self._hover = v
        self._draw()

    def pulse(self, muted: bool):
        """Expanding ring fades from accent → BG color."""
        hi  = MUTED_HI  if muted else LIVE_HI
        bg6 = BG[1:]
        s, c = self._s, self._c
        r0   = c // 2      # start radius = circle edge
        dr   = self.PAD - 2
        STEPS= 18

        def tick(n):
            self.delete("pulse")
            t    = n / STEPS
            ease = 1 - (1-t)**2
            col  = _lerp(hi, BG, ease)
            r    = r0 + int(ease * dr)
            cx, cy = s//2, s//2
            self.create_oval(cx-r, cy-r, cx+r, cy+r,
                             outline=col, width=max(1, int(3*(1-ease))),
                             tags="pulse")
            self.tag_raise("main")
            if n < STEPS: self.after(22, tick, n+1)
            else:         self.delete("pulse")
        tick(0)

    def update_state(self, muted: bool):
        self._muted = muted
        self._draw()
        self.pulse(muted)


# ── Glass card frame ──────────────────────────────────────────────────────────
def _glass_card(parent, **kw):
    """A frame styled as a glassmorphism card."""
    f = tk.Frame(parent, bg=CARD, **kw)
    f.config(highlightbackground=BORDER_HI, highlightthickness=1)
    return f


# ── Main window ───────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("shutIT")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.protocol("WM_DELETE_WINDOW", self._hide_to_tray)

        w, h = 340, 460
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        avail = tkfont.families()
        fam   = "Space Grotesk" if "Space Grotesk" in avail else "Segoe UI"
        self._ft = lambda sz, wt="normal": tkfont.Font(family=fam, size=sz, weight=wt)

        self._muted       = mic_logic.get_mute_state()
        self._startup_var = tk.BooleanVar(value=mic_logic.is_startup_enabled())
        self._tray        = None

        self._build()
        # Apply DWM glass after window is realized
        self.after(80, self._glass)
        self._start_tray()

    def _glass(self):
        try:
            self.update_idletasks()
            hwnd = windll.user32.GetParent(self.winfo_id())
            if not hwnd: hwnd = self.winfo_id()
            _apply_acrylic(hwnd)
            self.wm_attributes("-alpha", 0.93)
        except Exception:
            pass

    def _build(self):
        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=24, pady=(22,0))
        tk.Label(hdr, text="shutIT",   font=self._ft(17,"bold"), bg=BG, fg=TEXT_PRI).pack(side="left")
        tk.Label(hdr, text="mic muter",font=self._ft(10),        bg=BG, fg=TEXT_SEC).pack(side="left", padx=(8,0), pady=(5,0))

        # ── Body ──────────────────────────────────────────────────────────────
        mid = tk.Frame(self, bg=BG)
        mid.pack(expand=True, fill="both", padx=24)

        self._icon_btn = IconButton(mid, self._muted, command=self._toggle, circle=110)
        self._icon_btn.pack(pady=(16, 10))

        # Colored status
        self._status_lbl = tk.Label(
            mid, text=self._status_text(), font=self._ft(13,"bold"),
            bg=BG, fg=MUTED_HI if self._muted else LIVE_HI,
        )
        self._status_lbl.pack()

        # Hotkey hint
        tk.Label(mid, text="Right Ctrl  +  Right Shift",
                 font=self._ft(9), bg=BG, fg=TEXT_SEC).pack(pady=(5,0))

        # ── Divider ───────────────────────────────────────────────────────────
        tk.Frame(mid, bg=BORDER, height=1).pack(fill="x", pady=22)

        # ── Settings card (glassmorphism card) ────────────────────────────────
        card = _glass_card(mid, padx=16, pady=12)
        card.pack(fill="x")
        tk.Label(card, text="Run on startup", font=self._ft(10),
                 bg=CARD, fg=TEXT_PRI).pack(side="left")
        ToggleSwitch(card, self._startup_var, command=self._toggle_startup, bg=CARD).pack(side="right")

        # ── Footer ────────────────────────────────────────────────────────────
        ft = tk.Frame(self, bg=BG)
        ft.pack(fill="x", padx=24, pady=14, side="bottom")
        q = tk.Label(ft, text="Quit", font=self._ft(10), bg=BG, fg=TEXT_SEC, cursor="hand2")
        q.pack(side="right")
        q.bind("<Button-1>", lambda _: self._quit())
        q.bind("<Enter>",    lambda _: q.config(fg=TEXT_PRI))
        q.bind("<Leave>",    lambda _: q.config(fg=TEXT_SEC))

    # ── Tray ──────────────────────────────────────────────────────────────────
    def _start_tray(self):
        self._tray = pystray.Icon("shutIT", _tray_img(self._muted),
            f"shutIT – {'MUTED' if self._muted else 'LIVE'}",
            menu=pystray.Menu(
                pystray.MenuItem("Show",        self._show_from_tray, default=True),
                pystray.MenuItem("Toggle Mute", lambda *_: self.after(0, self._toggle)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Exit",        self._quit),
            ))
        threading.Thread(target=self._tray.run, daemon=True).start()

    def _update_tray(self, muted):
        if self._tray:
            self._tray.icon  = _tray_img(muted)
            self._tray.title = f"shutIT – {'MUTED' if muted else 'LIVE'}"

    def _show_from_tray(self, *_):
        self.after(0, self.deiconify); self.after(0, self.lift); self.after(0, self.focus_force)

    def _hide_to_tray(self): self.withdraw()

    # ── Logic ─────────────────────────────────────────────────────────────────
    def _toggle(self):
        threading.Thread(
            target=lambda: self.after(0, self._refresh, mic_logic.toggle_mute()),
            daemon=True,
        ).start()

    def _anim_color(self, f, t, steps=12, n=0):
        self._status_lbl.config(fg=_lerp(f, t, n/steps))
        if n < steps: self.after(16, self._anim_color, f, t, steps, n+1)

    def _refresh(self, muted: bool):
        old, new = (LIVE_HI, MUTED_HI) if muted else (MUTED_HI, LIVE_HI)
        self._muted = muted
        self._icon_btn.update_state(muted)
        self._status_lbl.config(text=self._status_text())
        self._anim_color(old, new)
        self._update_tray(muted)

    def _status_text(self): return "MUTED" if self._muted else "UNMUTED"
    def _toggle_startup(self): mic_logic.set_startup(self._startup_var.get())

    def _quit(self, *_):
        if self._tray: self._tray.stop()
        self.after(0, self.destroy)
