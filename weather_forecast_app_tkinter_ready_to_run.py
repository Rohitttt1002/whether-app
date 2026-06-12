r"""
Weather Forecast — CustomTkinter Enhanced Edition
Save as:
  C:\Users\LAPTOP WORLD\Downloads\project\weather_forecast_app_customtk.py

Requirements:
  pip install customtkinter pillow requests

Notes:
 - Uses images from IMG_DIR and fonts from FONT_DIR (paths below). Uses STATIC_BG for the large background.
 - Replace API_KEY with your own weatherapi.com key if desired.
"""

import os
import math
import time
import threading
import traceback
from datetime import datetime
from io import BytesIO

# External libs
try:
    import requests
except Exception as e:
    raise RuntimeError("Please install requests: python -m pip install requests") from e

try:
    from PIL import Image, ImageTk, ImageFilter, ImageDraw, ImageFont, ImageOps
except Exception as e:
    raise RuntimeError("Please install Pillow: python -m pip install pillow") from e

try:
    import customtkinter as ctk
except Exception as e:
    raise RuntimeError("Please install customtkinter: python -m pip install customtkinter") from e

# ----------------- CONFIG -----------------
API_KEY = "c68890bdce28419385675204252910"  # you may replace with your own key
BASE_CURRENT = "https://api.weatherapi.com/v1/current.json"
BASE_FORECAST = "https://api.weatherapi.com/v1/forecast.json"

# IMPORTANT: raw strings avoid Windows unicodeescape errors
IMG_DIR = r"C:\Users\LAPTOP WORLD\Downloads\project\images"
FONT_DIR = r"C:\Users\LAPTOP WORLD\Downloads\project\fonts"
STATIC_BG = r"C:\Users\LAPTOP WORLD\Downloads\project\images.jpeg"  # large background (optional)

DEFAULT_CITY = "Mumbai"
DAYS_FORECAST = 5
WINDOW_W, WINDOW_H = 1200, 740

# ----------------- UTILITIES -----------------
def now_ts():
    return int(time.time())

def safe_get(d, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
    return d if d is not None else default

# ----------------- ASSET SCANNING -----------------
def find_image_files(img_dir=IMG_DIR):
    result = {}
    if not os.path.isdir(img_dir):
        return result
    for root, _, files in os.walk(img_dir):
        for f in files:
            name = f.lower()
            if name.endswith((".png", ".jpg", ".jpeg", ".webp", ".svg")):
                path = os.path.join(root, f)
                result[f] = path
    return result

def find_font_files(font_dir=FONT_DIR):
    out = []
    if not os.path.isdir(font_dir):
        return out
    for f in os.listdir(font_dir):
        if f.lower().endswith(".ttf"):
            out.append(os.path.join(font_dir, f))
    return out

IMAGE_FILES = find_image_files()
FONT_FILES = find_font_files()

# ----------------- SIMPLE CACHE -----------------
class SimpleCache:
    def __init__(self):
        self._d = {}
    def set(self, k, v, ttl=600):
        self._d[k] = (v, now_ts() + ttl)
    def get(self, k):
        v = self._d.get(k)
        if not v: return None
        val, exp = v
        if now_ts() > exp:
            del self._d[k]
            return None
        return val

cache = SimpleCache()

# ----------------- WEATHER CLIENT -----------------
class WeatherClient:
    def __init__(self, key):
        self.key = key
    def current(self, city):
        params = {"key": self.key, "q": city}
        r = requests.get(BASE_CURRENT, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    def forecast(self, city, days=DAYS_FORECAST):
        params = {"key": self.key, "q": city, "days": days, "aqi": "no", "alerts": "no"}
        r = requests.get(BASE_FORECAST, params=params, timeout=12)
        r.raise_for_status()
        return r.json()

# ----------------- ICON SELECTION & DRAWING -----------------
def program_icon(kind, size=(256,256)):
    im = Image.new("RGBA", size, (0,0,0,0))
    draw = ImageDraw.Draw(im)
    w,h = size
    if kind == "sun":
        cx,cy = w//2, h//2
        draw.ellipse((cx-60, cy-60, cx+60, cy+60), fill=(255,220,80,255))
        for a in range(0,360,22):
            r = math.radians(a)
            x1 = cx + math.cos(r)*90
            y1 = cy + math.sin(r)*90
            x2 = cx + math.cos(r)*122
            y2 = cy + math.sin(r)*122
            draw.line((x1,y1,x2,y2), fill=(255,210,70,200), width=6)
    elif kind == "cloud":
        draw.ellipse((w*0.18,h*0.4,w*0.46,h*0.68), fill=(230,235,240,255))
        draw.ellipse((w*0.36,h*0.28,w*0.74,h*0.62), fill=(230,235,240,255))
    elif kind == "rain":
        draw.ellipse((w*0.14,h*0.22,w*0.54,h*0.44), fill=(200,210,220,255))
        for i,x in enumerate([w*0.34, w*0.46, w*0.58]):
            draw.line((x, h*0.54, x-8, h*0.82), fill=(60,120,200,255), width=8)
    else:
        draw.rectangle((w*0.2,h*0.3,w*0.8,h*0.6), fill=(170,180,200,255))
    return im

def choose_icon_for_text(text):
    t = (text or "").lower()
    # try to find a matching image file (filename contains keywords)
    for fname, path in IMAGE_FILES.items():
        ln = fname.lower()
        if "sun" in ln and ("sun" in t or "clear" in t):
            try:
                return Image.open(path).convert("RGBA")
            except Exception:
                continue
        if "cloud" in ln and ("cloud" in t or "overcast" in t):
            try:
                return Image.open(path).convert("RGBA")
            except Exception:
                continue
        if "rain" in ln and ("rain" in t or "drizzle" in t):
            try:
                return Image.open(path).convert("RGBA")
            except Exception:
                continue
        if "storm" in ln and ("thunder" in t or "storm" in t):
            try:
                return Image.open(path).convert("RGBA")
            except Exception:
                continue
        if "snow" in ln and ("snow" in t):
            try:
                return Image.open(path).convert("RGBA")
            except Exception:
                continue
    # fallback drawn icons
    if "rain" in t or "drizzle" in t:
        return program_icon("rain")
    if "snow" in t:
        return program_icon("cloud")
    if "cloud" in t or "overcast" in t:
        return program_icon("cloud")
    if "thunder" in t or "storm" in t:
        return program_icon("cloud")
    return program_icon("sun")

# ----------------- BACKGROUND UTIL -----------------
def load_background(target_w, target_h):
    if not os.path.exists(STATIC_BG):
        return None
    try:
        bg = Image.open(STATIC_BG).convert("RGBA")
        bw,bh = bg.size
        scale = max(target_w/bw, target_h/bh)
        nw, nh = int(bw*scale), int(bh*scale)
        bg = bg.resize((nw,nh), Image.LANCZOS)
        left = (nw - target_w)//2
        top = (nh - target_h)//2
        bg = bg.crop((left, top, left + target_w, top + target_h))
        bg = bg.filter(ImageFilter.GaussianBlur(radius=2.0))
        # darken overlay for contrast
        overlay = Image.new("RGBA", bg.size, (8,14,28,60))
        bg = Image.alpha_composite(bg, overlay)
        return bg
    except Exception:
        return None

# Create a "glass card" image: blurred rectangle from the background with semi-transparent white
def make_glass_panel(bg_img, panel_box, radius=18, tint=(255,255,255,150)):
    # panel_box = (x,y,w,h)
    if bg_img is None:
        # fallback: create semi-transparent rectangle
        w,h = panel_box[2], panel_box[3]
        panel = Image.new("RGBA", (w,h), tint)
        # rounded corners
        mask = Image.new("L", (w,h), 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0,0,w,h), radius=radius, fill=255)
        panel.putalpha(mask)
        return panel
    x,y,w,h = panel_box
    crop = bg_img.crop((x,y,x+w,y+h)).filter(ImageFilter.GaussianBlur(radius=8))
    overlay = Image.new("RGBA", (w,h), tint)
    result = Image.alpha_composite(crop.convert("RGBA"), overlay)
    # rounded corners mask
    mask = Image.new("L", (w,h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0,0,w,h), radius=radius, fill=255)
    result.putalpha(mask)
    return result

# ----------------- MAIN APP -----------------
class WeatherApp(ctk.CTk):
    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key
        self.client = WeatherClient(api_key)
        self.title("Weather Forecast — Enhanced (CustomTkinter)")
        self.geometry(f"{WINDOW_W}x{WINDOW_H}")
        self.minsize(900, 640)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # state
        self.city_var = ctk.StringVar(value=DEFAULT_CITY)
        self.unit_var = ctk.StringVar(value="C")
        self.status_var = ctk.StringVar(value="Ready")
        self.bg_image_pil = None
        self.bg_image_tk = None
        self._icon_cache = {}
        self._panel_imgs = {}
        self._forecast_data = []
        self._current_json = None

        # load background
        bg = load_background(WINDOW_W, WINDOW_H)
        if bg:
            self.bg_image_pil = bg
            self.bg_image_tk = ImageTk.PhotoImage(bg)
            self._bg_label = ctk.CTkLabel(self, image=self.bg_image_tk, text="")
            self._bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        # top bar
        self._build_topbar()

        # content area frames: left current, right forecast
        self._build_main_area()

        # bottom status
        self._build_statusbar()

        # theme toggle (top-right)
        self._theme_button = ctk.CTkButton(self.topbar_right, text="Toggle Theme", command=self._toggle_theme, width=120)
        self._theme_button.pack(side="right", padx=(6,12))

        # initial fetch
        self.after(300, lambda: self.fetch_weather(DEFAULT_CITY))

        # handle resize
        self.bind("<Configure>", self._on_resize_debounced)
        self._resize_job = None

    # ---------- UI BUILD ----------
    def _build_topbar(self):
        self.topbar = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent", height=72)
        self.topbar.place(relx=0, rely=0, relwidth=1)

        left = ctk.CTkFrame(self.topbar, fg_color="transparent")
        left.pack(side="left", anchor="w", padx=18, pady=10)
        lbl = ctk.CTkLabel(left, text="Weather Forecast", font=ctk.CTkFont(size=20, weight="bold"))
        lbl.pack(anchor="w")

        self.topbar_right = ctk.CTkFrame(self.topbar, fg_color="transparent")
        self.topbar_right.pack(side="right", anchor="e", padx=18)

        # city entry and search
        entry = ctk.CTkEntry(self.topbar_right, width=220, textvariable=self.city_var, placeholder_text="Enter city (e.g., London)")
        entry.pack(side="left", padx=(0,8))
        entry.bind("<Return>", lambda e: self.on_search())

        btn_search = ctk.CTkButton(self.topbar_right, text="Search", command=self.on_search)
        btn_search.pack(side="left", padx=6)

        btn_loc = ctk.CTkButton(self.topbar_right, text="Use My Location", command=self._geo_loc)
        btn_loc.pack(side="left", padx=6)

        # units
        units = ctk.CTkSegmentedButton(self.topbar_right, values=["C", "F"], variable=self.unit_var)
        units.pack(side="left", padx=10)

    def _build_main_area(self):
        # container
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.place(relx=0.02, rely=0.11, relwidth=0.96, relheight=0.78)

        # left: current weather card (we will render as image for glass effect)
        left_w = 0.34
        right_w = 1 - left_w - 0.02
        # left frame placeholder
        self.left_frame = ctk.CTkCanvas(self.container, bg="transparent", highlightthickness=0)
        self.left_frame.place(relx=0.01, rely=0.02, relwidth=left_w, relheight=0.96)
        # right scrollable frame for forecast
        self.right_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.right_frame.place(relx=0.36, rely=0.02, relwidth=0.63, relheight=0.96)

        # inside right: header + scroll
        header = ctk.CTkLabel(self.right_frame, text=f"{DAYS_FORECAST}-Day Forecast", font=ctk.CTkFont(size=16, weight="bold"))
        header.pack(anchor="nw", padx=12, pady=(8,6))

        # scrollable forecast area
        self._forecast_scroll = ctk.CTkScrollableFrame(self.right_frame, width=400, height=500, corner_radius=12)
        self._forecast_scroll.pack(fill="both", expand=True, padx=12, pady=(0,12))

        # placeholders for current weather widgets (drawn onto glass panel)
        self._current_widgets = {}  # keep text for updates
        # We'll draw a glass panel image and paste icon/text via PIL then convert to Tk image
        self._render_current_card()

    def _build_statusbar(self):
        self.status = ctk.CTkLabel(self, textvariable=self.status_var, anchor="w")
        self.status.place(relx=0.02, rely=0.92, relwidth=0.96, relheight=0.06)

    # ---------- PANEL RENDER ----------
    def _render_current_card(self):
        # compute pixel box within the left_frame's current size
        try:
            # size of left_frame in pixels
            w = int(self.winfo_width() * 0.34) or int(WINDOW_W * 0.34)
            h = int(self.winfo_height() * 0.78) or int(WINDOW_H * 0.78)
            # create glass panel image
            if self.bg_image_pil:
                # compute top-left pos of left_frame relative to window
                abs_x = int(self.winfo_width() * 0.02)
                abs_y = int(self.winfo_height() * 0.11)
                box = (abs_x + 6, abs_y + 6, int(w - 12), int(h - 12))
                panel = make_glass_panel(self.bg_image_pil, (box[0], box[1], box[2], box[3]), radius=18, tint=(255,255,255,140))
            else:
                panel = make_glass_panel(None, (0,0,w,h), radius=18, tint=(255,255,255,180))
            # add some static text placeholders
            draw = ImageDraw.Draw(panel)
            # choose a font (fallback)
            pil_font = None
            for fpath in FONT_FILES:
                try:
                    pil_font = ImageFont.truetype(fpath, 22)
                    break
                except Exception:
                    pil_font = ImageFont.load_default()
            # write "City" placeholder
            draw.text((22,18), "City, Country", fill=(20,40,80,255), font=pil_font)
            # convert to tk image and display in left_frame
            tk_img = ImageTk.PhotoImage(panel)
            self._panel_imgs["current"] = tk_img
            self.left_frame.delete("all")
            self.left_frame.create_image(0,0, anchor="nw", image=tk_img)
            # save panel dims for future drawing
            self._current_panel_size = panel.size
        except Exception:
            pass

    def _update_current_card(self, city_name, temp_text, cond_text, humidity, wind, pressure, time_text, pil_icon=None):
        # Render a new glass panel with the icon and text and push to canvas with a simple fade animation
        try:
            w,h = self._current_panel_size if hasattr(self, "_current_panel_size") else (360,420)
            # create base glass panel (semi-transparent)
            if self.bg_image_pil:
                abs_x = int(self.winfo_width() * 0.02)
                abs_y = int(self.winfo_height() * 0.11)
                panel = make_glass_panel(self.bg_image_pil, (abs_x+6, abs_y+6, w, h), radius=18, tint=(255,255,255,160))
            else:
                panel = make_glass_panel(None, (0,0,w,h), radius=18, tint=(255,255,255,200))
            draw = ImageDraw.Draw(panel)
            # fonts
            def get_font(sz=18):
                for f in FONT_FILES:
                    try:
                        return ImageFont.truetype(f, sz)
                    except Exception:
                        continue
                return ImageFont.load_default()
            f_title = get_font(22)
            f_large = get_font(48)
            f_small = get_font(16)
            # paste icon on left
            if pil_icon:
                icon = pil_icon.resize((160,160), Image.LANCZOS).convert("RGBA")
            else:
                icon = program_icon("sun", (160,160)).convert("RGBA")
            panel.paste(icon, (20, 60), icon)

            # texts
            draw.text((200, 26), city_name, font=f_title, fill=(10,10,30,255))
            draw.text((200, 70), temp_text, font=f_large, fill=(10,90,180,255))
            draw.text((200, 130), cond_text, font=f_small, fill=(30,40,60,220))
            # stats
            draw.text((22, 240), f"Humidity: {humidity}%", font=f_small, fill=(30,40,60,220))
            draw.text((22, 270), f"Wind: {wind} kph", font=f_small, fill=(30,40,60,220))
            draw.text((22, 300), f"Pressure: {pressure} hPa", font=f_small, fill=(30,40,60,220))
            draw.text((22, 330), f"Local time: {time_text}", font=f_small, fill=(30,40,60,220))

            # convert to tk image
            tkimg = ImageTk.PhotoImage(panel)
            self._panel_imgs["current"] = tkimg

            # simple fade-in effect: place and adjust alpha using canvas layers (simulate by quick swaps)
            self.left_frame.delete("all")
            self.left_frame.create_image(0,0, anchor="nw", image=tkimg)
        except Exception as e:
            print("Update current card error:", e)

    # ---------- SEARCH / GEO / EXPORT ----------
    def on_search(self):
        city = self.city_var.get().strip()
        if not city:
            ctk.CTkMessagebox.show_warning(title="Input", message="Please enter a city name (e.g., London)")
            return
        cache.set("last_city", city)
        self.fetch_weather(city)

    def _geo_loc(self):
        def task():
            try:
                self.status_var.set("Locating...")
                r = requests.get("http://ip-api.com/json/", timeout=8)
                r.raise_for_status()
                j = r.json()
                city = j.get("city") or j.get("regionName") or j.get("country")
                if city:
                    self.city_var.set(city)
                    self.fetch_weather(city)
                else:
                    ctk.CTkMessagebox.show_info(title="Location", message="Could not detect location")
            except Exception as e:
                ctk.CTkMessagebox.show_error(title="Location error", message=str(e))
            finally:
                self.status_var.set("Ready")
        threading.Thread(target=task, daemon=True).start()

    # ---------- THEME ----------
    def _toggle_theme(self):
        current = ctk.get_appearance_mode()
        ctk.set_appearance_mode("light" if current == "dark" else "dark")
        # regenerate background overlay to keep contrast
        if self.bg_image_pil:
            # recolor overlay slightly
            self.bg_image_tk = ImageTk.PhotoImage(self.bg_image_pil)
            try:
                self._bg_label.configure(image=self.bg_image_tk)
            except Exception:
                pass

    # ---------- RESIZE ----------
    def _on_resize_debounced(self, event):
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(220, self._on_resize)

    def _on_resize(self):
        # re-render background and current card size
        try:
            w = max(self.winfo_width(), 400)
            h = max(self.winfo_height(), 300)
            bg = load_background(w, h)
            if bg:
                self.bg_image_pil = bg
                self.bg_image_tk = ImageTk.PhotoImage(self.bg_image_pil)
                if hasattr(self, "_bg_label"):
                    self._bg_label.configure(image=self.bg_image_tk)
            # re-render current card and keep forecast layout
            self._render_current_card()
        except Exception:
            pass

    # ---------- FETCH WEATHER ----------
    def fetch_weather(self, city):
        def task():
            cache_key = f"w::{city}"
            cached = cache.get(cache_key)
            if cached:
                self.after(0, lambda: self._display(cached["current"], cached["forecast"]))
                return
            try:
                self.status_var.set("Fetching current...")
                cur = self.client.current(city)
                self.status_var.set("Fetching forecast...")
                fj = self.client.forecast(city, days=DAYS_FORECAST)
                daily = []
                for day in fj.get("forecast", {}).get("forecastday", []):
                    dd = {
                        "date": day.get("date"),
                        "label": datetime.strptime(day.get("date"), "%Y-%m-%d").strftime("%a, %b %d"),
                        "condition": safe_get(day, "day", "condition", "text", default="-"),
                        "avg_c": safe_get(day, "day", "avgtemp_c", default="-"),
                        "avg_f": safe_get(day, "day", "avgtemp_f", default="-"),
                        "max_c": safe_get(day, "day", "maxtemp_c", default="-"),
                        "min_c": safe_get(day, "day", "mintemp_c", default="-"),
                        "precip_mm": safe_get(day, "day", "totalprecip_mm", default=0),
                    }
                    daily.append(dd)
                cache.set(cache_key, {"current": cur, "forecast": daily}, ttl=300)
                self.after(0, lambda: self._display(cur, daily))
            except Exception as e:
                tb = traceback.format_exc()
                print(tb)
                try:
                    ctk.CTkMessagebox.show_error(title="Fetch error", message=str(e))
                except Exception:
                    pass
                self.status_var.set("Error")
            finally:
                self.after(0, lambda: self.status_var.set("Ready"))
        threading.Thread(target=task, daemon=True).start()

    # ---------- DISPLAY ----------
    def _display(self, current_json, forecast_list):
        try:
            self._current_json = current_json
            self._forecast_data = forecast_list
            location = current_json.get("location", {})
            current = current_json.get("current", {})

            city_name = f"{location.get('name','-')}, {location.get('country','-')}"
            temp_c = current.get("temp_c", "--")
            temp_f = current.get("temp_f", "--")
            unit = self.unit_var.get()
            temp_text = f"{round(temp_c)} °C" if unit == "C" else f"{round(temp_f)} °F"
            cond = safe_get(current, "condition", "text", default="-")
            humidity = current.get("humidity", "-")
            wind = current.get("wind_kph", "-")
            pressure = current.get("pressure_mb", "-")
            local_ts = location.get("localtime_epoch")
            local_time = datetime.fromtimestamp(local_ts).strftime("%H:%M") if local_ts else "-"

            # choose icon (PIL)
            pil_icon = choose_icon_for_text(cond)

            # update current card
            self._update_current_card(city_name, temp_text, cond, humidity, wind, pressure, local_time, pil_icon=pil_icon)

            # populate forecast scroll (clear)
            for w in self._forecast_scroll.winfo_children():
                w.destroy()

            for d in forecast_list:
                self._make_forecast_card(d)

        except Exception as e:
            print("Display error:", e)

    def _make_forecast_card(self, d):
        # create a small glass image for card background and place labels and icon
        try:
            # card container frame
            card = ctk.CTkFrame(self._forecast_scroll, corner_radius=12, fg_color="transparent")
            card.pack(fill="x", padx=6, pady=8)

            # left icon
            icon_pil = choose_icon_for_text(d.get("condition","-"))
            icon_pil = icon_pil.resize((80,80), Image.LANCZOS).convert("RGBA")
            tk_icon = ImageTk.PhotoImage(icon_pil)
            # keep reference
            if not hasattr(self, "_tk_icons"):
                self._tk_icons = []
            self._tk_icons.append(tk_icon)

            icon_label = ctk.CTkLabel(card, image=tk_icon, text="")
            icon_label.grid(row=0, column=0, rowspan=2, padx=10, pady=8)

            # date and condition
            lbl_date = ctk.CTkLabel(card, text=d.get("label","-"), anchor="w", font=ctk.CTkFont(size=14, weight="bold"))
            lbl_date.grid(row=0, column=1, sticky="w", padx=8, pady=(12,0))

            lbl_cond = ctk.CTkLabel(card, text=d.get("condition","-"), anchor="w", font=ctk.CTkFont(size=12))
            lbl_cond.grid(row=1, column=1, sticky="w", padx=8, pady=(0,8))

            stats = ctk.CTkLabel(card, text=f"Avg: {d.get('avg_c')}°C  Max: {d.get('max_c')}°C  Min: {d.get('min_c')}°C", anchor="e")
            stats.grid(row=0, column=2, rowspan=2, sticky="e", padx=10)
        except Exception as e:
            print("Make forecast card error:", e)

# ----------------- ENTRY POINT -----------------
def main():
    if not API_KEY or API_KEY.startswith("REPLACE"):
        print("Please set a valid WeatherAPI API_KEY inside the script.")
        return
    app = WeatherApp(API_KEY)
    app.mainloop()

if __name__ == "__main__":
    main()
