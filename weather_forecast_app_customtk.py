

import os
import time
import math
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import requests
import tkinter as tk
from tkinter import messagebox as mb

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageTk, ImageFilter

# ---------------- Configuration ----------------
API_KEY = "c68890bdce28419385675204252910"  # your WeatherAPI.com key
WEATHER_CURRENT = "https://api.weatherapi.com/v1/current.json"
WEATHER_FORECAST = "https://api.weatherapi.com/v1/forecast.json"

DEFAULT_CITY = "Mumbai"
DEFAULT_FORECAST_DAYS = 7
MIN_WIN_W, MIN_WIN_H = 980, 680
INIT_WIN_W, INIT_WIN_H = 1240, 760

# Path to user background image
USER_BG_PATH ="C:/Users/LAPTOP WORLD/Downloads/project/images.jpeg"
# Colors (dark UI but background will be user's image)
COLOR_BG = "#071428"
COLOR_PANEL = "#0b1b32"
COLOR_CARD = "#0f172a"
COLOR_ACCENT = "#ffdd66"
COLOR_TEXT = "#FFFFFF"
COLOR_MUTED = "#9fb0c8"
COLOR_ERROR = "#ef4444"

# ---------------- Utilities ----------------
def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def ts_now():
    return int(time.time())

def round_if_number(x) -> str:
    return f"{round(x)}" if isinstance(x, (int, float)) else str(x)

def load_font(size: int):
    names = ["Inter", "Segoe UI", "Arial", "Roboto", "Helvetica", "Ubuntu"]
    for name in names:
        try:
            return ImageFont.truetype(name + ".ttf", size=size)
        except Exception:
            continue
    return ImageFont.load_default()

# ---------------- Simple cache ----------------
class TimedCache:
    def __init__(self):
        self._d: Dict[str, Tuple[dict, int]] = {}
    def get(self, k: str) -> Optional[dict]:
        item = self._d.get(k)
        if not item:
            return None
        v, exp = item
        if ts_now() > exp:
            self._d.pop(k, None)
            return None
        return v
    def set(self, k: str, v: dict, ttl: int = 300):
        self._d[k] = (v, ts_now() + ttl)

CACHE = TimedCache()

# ---------------- Icon Factory ----------------
class IconFactory:
    def __init__(self, scale=1.0):
        self.scale = scale
        self.override = self._scan_overrides()

    def _scan_overrides(self) -> Dict[str, str]:
        out = {}
        try:
            base_dir = os.path.dirname(__file__)
            icon_dir = os.path.join(base_dir, "assets", "icons")
            if not os.path.isdir(icon_dir):
                return out
            for f in os.listdir(icon_dir):
                lf = f.lower()
                if not lf.endswith(".png"):
                    continue
                p = os.path.join(icon_dir, f)
                for key in ["sun", "cloud", "rain", "snow", "storm", "wind", "droplet", "gauge", "uv"]:
                    if key in lf:
                        out[key] = p
        except Exception:
            pass
        return out

    def _load_override(self, key: str, size: Tuple[int,int]):
        p = self.override.get(key)
        if not p:
            return None
        try:
            return Image.open(p).convert("RGBA").resize(size, Image.LANCZOS)
        except Exception:
            return None

    def sun(self, size=(160,160)):
        if (img := self._load_override("sun", size)):
            return img
        w,h = size
        im = Image.new("RGBA", size, (0,0,0,0))
        d = ImageDraw.Draw(im)
        cx,cy = w//2, h//2
        d.ellipse((cx-42, cy-42, cx+42, cy+42), fill=COLOR_ACCENT)
        for i in range(12):
            ang = math.radians(i*30)
            x1 = cx + int(58*math.cos(ang)); y1 = cy + int(58*math.sin(ang))
            x2 = cx + int(76*math.cos(ang)); y2 = cy + int(76*math.sin(ang))
            d.line((x1,y1,x2,y2), fill=(255,220,110,230), width=4)
        return im

    def cloud(self, size=(180,120)):
        if (img := self._load_override("cloud", size)):
            return img
        w,h = size
        im = Image.new("RGBA", size, (0,0,0,0))
        d = ImageDraw.Draw(im)
        c = (235,243,255,230)
        d.ellipse((w*0.05, h*0.35, w*0.45, h*0.85), fill=c)
        d.ellipse((w*0.28, h*0.20, w*0.78, h*0.75), fill=c)
        return im

    def rain(self, size=(180,140)):
        if (img := self._load_override("rain", size)):
            return img
        im = self.cloud((size[0], size[1]-20)).copy()
        d = ImageDraw.Draw(im)
        w,h = im.size
        for x in [w*0.35, w*0.50, w*0.65]:
            d.line((x, h*0.70, x-10, h*1.00), fill=(70,130,220,255), width=5)
        return im

    def snow(self, size=(180,140)):
        if (img := self._load_override("snow", size)):
            return img
        im = self.cloud((size[0], size[1]-20)).copy()
        d = ImageDraw.Draw(im)
        w,h = im.size
        for x in [w*0.38, w*0.55, w*0.72]:
            d.text((x-6, h*0.78), "❄", fill=(220,240,255,255), font=load_font(18))
        return im

    def storm(self, size=(180,140)):
        if (img := self._load_override("storm", size)):
            return img
        im = self.cloud((size[0], size[1]-20)).copy()
        d = ImageDraw.Draw(im)
        w,h = im.size
        d.polygon([(w*0.60, h*0.65),(w*0.48,h*1.00),(w*0.70,h*0.95),(w*0.58,h*1.25)], fill=(255,210,90,255))
        return im

    def by_condition_text(self, text: str, size=(180,140)):
        t = (text or "").lower()
        if "thunder" in t or "storm" in t:
            return self.storm(size)
        if "snow" in t or "sleet" in t or "ice" in t:
            return self.snow(size)
        if "rain" in t or "drizzle" in t or "shower" in t:
            return self.rain(size)
        if "cloud" in t or "overcast" in t or "fog" in t or "mist" in t or "haze" in t:
            return self.cloud(size)
        return self.sun(size)

# ---------------- Weather Client ----------------
class WeatherClient:
    def __init__(self, key: str):
        self.key = key

    def current(self, q: str) -> dict:
        params = {"key": self.key, "q": q, "aqi": "no"}
        r = requests.get(WEATHER_CURRENT, params=params, timeout=12)
        r.raise_for_status()
        return r.json()

    def forecast(self, q: str, days: int = DEFAULT_FORECAST_DAYS) -> dict:
        params = {"key": self.key, "q": q, "days": clamp(days, 1, 10), "aqi": "no", "alerts": "no"}
        r = requests.get(WEATHER_FORECAST, params=params, timeout=15)
        r.raise_for_status()
        return r.json()

# ---------------- Data Models ----------------
@dataclass
class CurrentWeather:
    city: str = "-"
    country: str = "-"
    temp_c: float = 0.0
    temp_f: float = 0.0
    feelslike_c: float = 0.0
    feelslike_f: float = 0.0
    humidity: int = 0
    wind_kph: float = 0.0
    pressure_mb: float = 0.0
    condition: str = "-"
    uv: float = 0.0
    local_epoch: int = 0

    @staticmethod
    def from_api(j: dict) -> "CurrentWeather":
        loc = j.get("location", {})
        cur = j.get("current", {})
        return CurrentWeather(
            city=loc.get("name", "-"),
            country=loc.get("country", "-"),
            temp_c=cur.get("temp_c", 0.0),
            temp_f=cur.get("temp_f", 0.0),
            feelslike_c=cur.get("feelslike_c", 0.0),
            feelslike_f=cur.get("feelslike_f", 0.0),
            humidity=cur.get("humidity", 0),
            wind_kph=cur.get("wind_kph", 0.0),
            pressure_mb=cur.get("pressure_mb", 0.0),
            condition=(cur.get("condition", {}) or {}).get("text", "-"),
            uv=cur.get("uv", 0.0),
            local_epoch=loc.get("localtime_epoch", 0),
        )

@dataclass
class DailyForecast:
    date_epoch: int
    label: str
    condition: str
    max_c: float
    min_c: float
    max_f: float
    min_f: float
    daily_chance_of_rain: int

    @staticmethod
    def list_from_api(j: dict) -> List["DailyForecast"]:
        out: List[DailyForecast] = []
        f = (j.get("forecast", {}) or {}).get("forecastday", []) or []
        for day in f:
            date_str = day.get("date")
            try:
                epoch = int(datetime.strptime(date_str, "%Y-%m-%d").timestamp())
            except Exception:
                epoch = int(time.time())
            dday = day.get("day", {}) or {}
            out.append(DailyForecast(
                date_epoch=epoch,
                label=datetime.fromtimestamp(epoch).strftime("%a"),
                condition=(dday.get("condition", {}) or {}).get("text", "-"),
                max_c=dday.get("maxtemp_c", 0.0),
                min_c=dday.get("mintemp_c", 0.0),
                max_f=dday.get("maxtemp_f", 0.0),
                min_f=dday.get("mintemp_f", 0.0),
                daily_chance_of_rain=int(dday.get("daily_chance_of_rain", 0)),
            ))
        return out

# ---------------- Graphics helpers ----------------
def gradient_background(size: Tuple[int,int]):
    w,h = size
    im = Image.new("RGBA", size, (7,20,40,255))
    d = ImageDraw.Draw(im)
    cx,cy = int(w*0.25), int(h*0.25)
    max_r = int(math.hypot(w,h))
    for i in range(max_r, 0, -24):
        a = int(180 * (i/max_r))
        color = (10, 40, 80, a)
        d.ellipse((cx-i, cy-i, cx+i, cy+i), fill=color)
    haze = Image.new("RGBA", size, (255,255,255,12))
    return Image.alpha_composite(im, haze)

# ---------------- Main App ----------------
class WeatherApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Weather Dashboard")
        self.geometry(f"{INIT_WIN_W}x{INIT_WIN_H}")
        self.minsize(MIN_WIN_W, MIN_WIN_H)

        # Theme default
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # State
        self.client = WeatherClient(API_KEY)
        self.icon_factory = IconFactory()
        self.unit = tk.StringVar(value="C")
        self.city_var = tk.StringVar(value=DEFAULT_CITY)
        self.status_var = tk.StringVar(value="Ready")
        self.bg_pil: Optional[Image.Image] = None
        self.bg_tk: Optional[ImageTk.PhotoImage] = None
        self.user_bg_pil: Optional[Image.Image] = None
        self.user_bg_tk: Optional[ImageTk.PhotoImage] = None
        self.left_img_tk: Optional[ImageTk.PhotoImage] = None
        self._tk_icon_refs: List[ImageTk.PhotoImage] = []
        self._current: Optional[CurrentWeather] = None
        self._forecast: List[DailyForecast] = []

        # Root color (fallback)
        self.configure(fg_color=COLOR_BG)

        # Background (will try user image)
        self._render_background(INIT_WIN_W, INIT_WIN_H)
        self.bg_label = ctk.CTkLabel(self, text="", image=self.bg_tk)
        self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        # UI
        self._build_topbar()
        self._build_content()
        self._build_statusbar()

        # Events and initial fetch
        self.bind("<Configure>", self._debounce_resize)
        self.after(200, lambda: self._fetch_weather(self.city_var.get()))

    # small helpers
    def _label(self, parent, text, size=14, bold=False, **kwargs):
        return ctk.CTkLabel(parent, text=text, text_color=COLOR_TEXT,
                            font=ctk.CTkFont(size=size, weight="bold" if bold else "normal"),
                            **kwargs)

    def _button(self, parent, text, command=None, width=None, **kwargs):
        return ctk.CTkButton(parent, text=text, width=width, command=command, text_color=COLOR_TEXT, **kwargs)

    # UI build
    def _build_topbar(self):
        self.topbar = ctk.CTkFrame(self, fg_color="#081426", corner_radius=0, height=64)
        self.topbar.pack(side="top", fill="x")

        title = self._label(self.topbar, "Weather Dashboard", size=18, bold=True)
        title.pack(side="left", padx=16)

        search_frame = ctk.CTkFrame(self.topbar, fg_color="#071a2a")
        search_frame.pack(side="right", padx=10)

        self.search_entry = ctk.CTkEntry(search_frame, width=320, textvariable=self.city_var,
                                         placeholder_text="Enter city (e.g., London)",
                                         text_color=COLOR_TEXT, placeholder_text_color=COLOR_MUTED)
        self.search_entry.pack(side="left", padx=(0,8), pady=12)
        self.search_entry.bind("<Return>", lambda e: self._on_search())

        btn_search = self._button(search_frame, "Search", command=self._on_search, width=100)
        btn_search.pack(side="left", padx=6)

        unit = ctk.CTkSegmentedButton(search_frame, values=["C","F"], variable=self.unit,
                                      command=lambda v: self._render_left_card())
        unit.pack(side="left", padx=(12,6))

        theme_btn = self._button(search_frame, "Toggle Theme", command=self._toggle_theme, width=110)
        theme_btn.pack(side="left", padx=(8,12))

    def _build_content(self):
        self.content = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=0)
        self.content.pack(side="top", fill="both", expand=True)

        left_bg = self.cget("fg_color") if "fg_color" in self.keys() else COLOR_PANEL
        self.left_canvas = tk.Canvas(self.content, bg=left_bg, highlightthickness=0)
        self.left_canvas.place(relx=0.03, rely=0.08, relwidth=0.4, relheight=0.8)

        self.left_image_label = ctk.CTkLabel(self.content, text="", text_color=COLOR_TEXT, anchor="n")
        self.left_image_label.place(relx=0.03, rely=0.08, relwidth=0.4, relheight=0.8)

        right_w = 0.51
        self.right = ctk.CTkFrame(self.content, fg_color="#0a1430", corner_radius=14)
        self.right.place(relx=0.46, rely=0.08, relwidth=right_w, relheight=0.8)

        header = self._label(self.right, "7-Day Forecast", size=16, bold=True)
        header.pack(anchor="nw", padx=16, pady=(12,6))

        self.forecast_container = ctk.CTkFrame(self.right, fg_color=COLOR_CARD, corner_radius=8)
        self.forecast_container.pack(fill="both", expand=True, padx=12, pady=(0,12))

    def _build_statusbar(self):
        self.statusbar = ctk.CTkFrame(self, fg_color="#05121a", height=28)
        self.statusbar.pack(side="bottom", fill="x")
        lbl = ctk.CTkLabel(self.statusbar, textvariable=self.status_var, text_color=COLOR_TEXT, anchor="w")
        lbl.pack(side="left", padx=8)

    # Background rendering: try user image natural (no dim). On resize, it rescales.
    def _render_background(self, w: int, h: int):
        # Try to load user's image once, keep PIL image in memory and resize per call
        if self.user_bg_pil is None:
            try:
                if os.path.isfile(USER_BG_PATH):
                    self.user_bg_pil = Image.open(USER_BG_PATH).convert("RGBA")
                else:
                    self.user_bg_pil = None
            except Exception:
                self.user_bg_pil = None

        if self.user_bg_pil:
            try:
                # resize preserving aspect to cover window (cover strategy)
                src = self.user_bg_pil
                sw, sh = src.size
                # compute scale to cover
                scale = max(w / sw, h / sh)
                nw, nh = int(sw * scale), int(sh * scale)
                resized = src.resize((nw, nh), Image.LANCZOS)
                # crop center
                left = (nw - w) // 2
                top = (nh - h) // 2
                cropped = resized.crop((left, top, left + w, top + h))
                self.bg_pil = cropped
                self.bg_tk = ImageTk.PhotoImage(self.bg_pil)
                return
            except Exception:
                self.user_bg_pil = None

        # fallback gradient background
        try:
            self.bg_pil = gradient_background((w,h))
            self.bg_tk = ImageTk.PhotoImage(self.bg_pil)
        except Exception:
            self.bg_pil = Image.new("RGBA", (w,h), COLOR_BG)
            self.bg_tk = ImageTk.PhotoImage(self.bg_pil)

    def _debounce_resize(self, event=None):
        if hasattr(self, "_resize_after_id"):
            try:
                self.after_cancel(self._resize_after_id)
            except Exception:
                pass
        self._resize_after_id = self.after(200, lambda: self._on_resize())

    def _on_resize(self):
        w = max(self.winfo_width(), MIN_WIN_W)
        h = max(self.winfo_height(), MIN_WIN_H)
        self._render_background(w, h)
        if self.bg_label:
            self.bg_label.configure(image=self.bg_tk)

    # Actions
    def _on_search(self):
        q = self.city_var.get().strip()
        if not q:
            mb.showinfo("Enter city", "Please type a city name first.")
            return
        self._set_status(f"Searching for {q}...")
        self._fetch_weather(q)

    def _set_status(self, text: str):
        self.status_var.set(text)

    def _fetch_weather(self, q: str):
        cached = CACHE.get(q)
        if cached:
            self.after(0, lambda: self._apply_api_results(cached))
            return

        def worker():
            try:
                cur_json = self.client.current(q)
                fore_json = self.client.forecast(q, days=DEFAULT_FORECAST_DAYS)
                combined = {
                    "location": cur_json.get("location"),
                    "current": cur_json.get("current"),
                    "forecast": fore_json.get("forecast")
                }
                CACHE.set(q, combined, ttl=300)
                self.after(0, lambda: self._apply_api_results(combined))
            except requests.HTTPError as he:
                self.after(0, lambda: mb.showerror("HTTP Error", f"{he}"))
                self.after(0, lambda: self._set_status("Error fetching data"))
            except Exception as e:
                self.after(0, lambda: mb.showerror("Error", f"Failed to fetch weather: {e}"))
                self.after(0, lambda: self._set_status("Error fetching data"))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_api_results(self, j: dict):
        try:
            current_shape = {"location": j.get("location", {}), "current": j.get("current", {})}
            self._current = CurrentWeather.from_api(current_shape)
            forecast_shape = {"forecast": j.get("forecast", {})}
            self._forecast = DailyForecast.list_from_api(forecast_shape)
        except Exception:
            self._current = None
            self._forecast = []

        self._render_left_card()
        self._render_forecast()
        self._set_status(f"Updated: {self._current.city if self._current else self.city_var.get()}")

    # Rendering
    def _render_left_card(self):
        if not self._current:
            txt = "No data"
            img = self.icon_factory.sun((260,220))
        else:
            unit = self.unit.get()
            temp = round_if_number(self._current.temp_c) if unit == "C" else round_if_number(self._current.temp_f)
            txt = f"{self._current.city}, {self._current.country}\n{temp}°{unit}\n{self._current.condition}"
            img = self.icon_factory.by_condition_text(self._current.condition, size=(260,220))

        try:
            pil_for_tk = img.convert("RGBA")
            tk_img = ImageTk.PhotoImage(pil_for_tk)
            self.left_img_tk = tk_img
            self.left_image_label.configure(image=self.left_img_tk, text=txt, compound="top", anchor="n")
            self.left_image_label.configure(text_color=COLOR_TEXT)
        except Exception:
            self.left_image_label.configure(text=txt, text_color=COLOR_TEXT)

    def _render_forecast(self):
        for child in self.forecast_container.winfo_children():
            child.destroy()
        self._tk_icon_refs.clear()

        if not self._forecast:
            lbl = ctk.CTkLabel(self.forecast_container, text="No forecast data", text_color=COLOR_TEXT)
            lbl.place(relx=0.5, rely=0.5, anchor="center")
            return

        for day in self._forecast:
            fr = ctk.CTkFrame(self.forecast_container, fg_color=COLOR_CARD, corner_radius=8)
            fr.pack(side="left", padx=8, pady=12, ipadx=8, ipady=8)

            lbl_day = ctk.CTkLabel(fr, text=day.label, text_color=COLOR_TEXT, font=ctk.CTkFont(size=14, weight="bold"))
            lbl_day.pack()

            icon_pil = self.icon_factory.by_condition_text(day.condition, size=(80,60))
            try:
                icon_tk = ImageTk.PhotoImage(icon_pil)
                self._tk_icon_refs.append(icon_tk)
                lbl_icon = ctk.CTkLabel(fr, image=icon_tk, text="")
                lbl_icon.pack(pady=(6,0))
            except Exception:
                ctk.CTkLabel(fr, text=day.condition[:10], text_color=COLOR_TEXT).pack()

            temp_text = f"{round_if_number(day.max_c)}°/{round_if_number(day.min_c)}° C"
            ctk.CTkLabel(fr, text=temp_text, text_color=COLOR_TEXT, font=ctk.CTkFont(size=12)).pack(pady=(6,0))
            ctk.CTkLabel(fr, text=f"Rain: {day.daily_chance_of_rain}%", text_color=COLOR_MUTED, font=ctk.CTkFont(size=11)).pack(pady=(2,0))

    def _toggle_theme(self):
        mode = ctk.get_appearance_mode()
        ctk.set_appearance_mode("light" if mode == "dark" else "dark")
        self._render_left_card()
        self._render_forecast()

# ---------- Run ----------
def main():
    # ensure pip packages installed before running this script
    app = WeatherApp()
    app.mainloop()

if __name__ == "__main__":
    main()
