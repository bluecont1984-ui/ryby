
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.list import MDList, TwoLineAvatarIconListItem, IconLeftWidget
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.dialog import MDDialog
from kivy.clock import Clock
from kivy.utils import platform
import requests
import datetime
import ephem
import math
import threading
import json
import os
from collections import Counter

# ======================================================
# 1. MENEDŻER HISTORII (FIX NA CRASH ANDROIDA)
# ======================================================
class CatchManager:
    def __init__(self, filename="catches.json"):
        self.filename = filename
        self.filepath = self.get_storage_path()
        self.ensure_file()

    def get_storage_path(self):
        if platform == 'android':
            try:
                from android.storage import app_storage_path
                app = MDApp.get_running_app()
                return os.path.join(app.user_data_dir, self.filename)
            except:
                return self.filename
        else:
            return self.filename

    def ensure_file(self):
        if not os.path.exists(self.filepath):
            try:
                with open(self.filepath, "w") as f:
                    json.dump([], f)
            except Exception as e:
                print(f"Błąd pliku: {e}")

    def save_catch(self, city, species, temp, pressure, wind_arrow, time_str):
        entry = {"city": city, "species": species, "time": time_str, "temp": temp, "pressure": pressure, "wind": wind_arrow}
        try:
            with open(self.filepath, "r") as f: history = json.load(f)
            history.append(entry)
            with open(self.filepath, "w") as f: json.dump(history, f, indent=4)
            return True
        except: return False

    def get_top_conditions(self, species):
        try:
            with open(self.filepath, "r") as f: history = json.load(f)
            relevant = [h['wind'] for h in history if h.get('species') == species]
            if not relevant: return None
            return Counter(relevant).most_common(1)[0][0]
        except: return None

# ======================================================
# 2. SILNIK DANYCH
# ======================================================
class RealDataEngine:
    def __init__(self):
        self.base_url_weather = "https://api.open-meteo.com/v1/forecast"
        self.base_url_geo = "https://geocoding-api.open-meteo.com/v1/search"
        self.catch_manager = CatchManager()
        self.profiles = {
            "Szczupak": {"type": "predator", "optimum": 12.0, "sigma": 6.0, "min_temp": -5.0, "is_vampire": False},
            "Sandacz": {"type": "predator", "optimum": 16.0, "sigma": 5.0, "min_temp": -2.0, "is_vampire": True},
            "Okoń": {"type": "predator", "optimum": 16.0, "sigma": 7.0, "min_temp": -5.0, "is_vampire": False},
            "Węgorz": {"type": "predator", "optimum": 22.0, "sigma": 4.0, "min_temp": 8.0, "is_vampire": True},
            "Karp": {"type": "peaceful", "optimum": 20.0, "sigma": 3.0, "min_temp": 5.0, "is_vampire": False},
            "Leszcz": {"type": "peaceful", "optimum": 18.0, "sigma": 4.0, "min_temp": 2.0, "is_vampire": False},
            "Lin": {"type": "peaceful", "optimum": 23.0, "sigma": 3.0, "min_temp": 8.0, "is_vampire": False},
            "Płoć": {"type": "peaceful", "optimum": 14.0, "sigma": 6.0, "min_temp": -5.0, "is_vampire": False}
        }
        self.current_species = "Szczupak"

    def set_species(self, species):
        if species in self.profiles: self.current_species = species

    def get_location(self, city_name):
        try:
            params = {"name": city_name, "count": 1, "language": "pl", "format": "json"}
            r = requests.get(self.base_url_geo, params=params)
            d = r.json()
            return d["results"][0] if "results" in d else None
        except: return None

    def get_real_weather(self, lat, lon):
        try:
            params = {"latitude": lat, "longitude": lon, "hourly": "temperature_2m,surface_pressure,rain,wind_speed_10m,wind_direction_10m,cloud_cover", "past_days": 3, "forecast_days": 2, "timezone": "auto"}
            r = requests.get(self.base_url_weather, params=params)
            return r.json()
        except: return None

    def get_wind_details(self, deg):
        arrows = ['↓', '↙', '←', '↖', '↑', '↗', '→', '↘']
        idx = round(deg / 45) % 8
        return arrows[idx]

    def estimate_water_temp(self, hourly_temps, current_idx):
        start_slice = max(0, current_idx - 72)
        history = hourly_temps[start_slice : current_idx + 1]
        if not history: return hourly_temps[current_idx]
        return round(sum(history) / len(history), 1)

    def analyze_data(self, hourly, idx, lat, lon):
        prof = self.profiles[self.current_species]
        is_predator = (prof["type"] == "predator")
        is_vampire = prof.get("is_vampire", False)
        optimum, min_temp = prof["optimum"], prof["min_temp"]

        temp = hourly['temperature_2m'][idx]
        water_temp = self.estimate_water_temp(hourly['temperature_2m'], idx)
        pressure = hourly['surface_pressure'][idx]
        rain = hourly['rain'][idx]
        wind_spd = hourly['wind_speed_10m'][idx]
        clouds = hourly['cloud_cover'][idx]
        wind_dir = hourly['wind_direction_10m'][idx]
        wind_arrow = self.get_wind_details(wind_dir)

        reasons = []
        current_score = 30

        if water_temp < min_temp:
            current_score -= 20; reasons.append(f"❄️ WODA {water_temp}°C: Za zimna")
        else:
            temp_quality = math.exp(-((water_temp - optimum) ** 2) / (2 * prof["sigma"] ** 2))
            current_score += int(temp_quality * 40)
            if temp_quality > 0.85: reasons.append(f"✅ Woda {water_temp}°C (Optimum)")
            else: reasons.append(f"ℹ️ Woda {water_temp}°C")

        p_old = hourly['surface_pressure'][max(0, idx - 24)]
        diff = pressure - p_old
        
        if diff < -1.0:
            if is_predator: current_score += 30; reasons.append("⚔️ Spadek ciśnienia!")
            else: current_score -= 20; reasons.append("❌ Spadek ciśnienia")
        elif diff > 1.5:
            if is_predator: current_score -= 15; reasons.append("❌ Wzrost ciśnienia")
            else: current_score += 15; reasons.append("🌿 Stabilizacja")
        
        dt = datetime.datetime.strptime(hourly['time'][idx], "%Y-%m-%dT%H:%M")
        obs = ephem.Observer(); obs.lat, obs.lon, obs.date = str(lat), str(lon), dt
        sun, moon = ephem.Sun(obs), ephem.Moon(obs)
        sun.compute(obs); moon.compute(obs)
        sun_alt = math.degrees(sun.alt)
        
        day_status = ""
        if -6 <= sun_alt <= 6:
            day_status = "🌅 ŚWIT/ZMIERZCH"; current_score += 20; reasons.append("✅ Złota godzina")
        elif sun_alt > 6:
            day_status = "☀️ DZIEŃ"
            if is_vampire:
                if clouds < 30: current_score -= 25; reasons.append("❌ Lampa")
                else: current_score += 5; reasons.append("✅ Pochmurno")
            else:
                if water_temp < 8 and clouds < 40: current_score += 10; reasons.append("☀️ Słońce grzeje")
                elif clouds < 20 and is_predator: current_score -= 10; reasons.append("❌ Lampa")
                else: current_score += 5
        else:
            day_status = "🌑 NOC"
            if is_vampire: current_score += 15; reasons.append("✅ Noc (Aktywność)")
            else: current_score -= 10; reasons.append("❌ Noc")

        best = self.catch_manager.get_top_conditions(self.current_species)
        if best == wind_arrow: current_score += 15; reasons.append(f"🏆 Twoja historia ({wind_arrow})")

        if wind_spd > 25: current_score -= 15; reasons.append("❌ Wichura")
        elif 6 <= wind_spd <= 20:
            if is_predator: current_score += 10; reasons.append("✅ Fala")
            else: current_score -= 5; reasons.append("🌿 Za duża fala")

        if rain > 2.0: current_score -= 10; reasons.append("❌ Ulewa")
        elif rain > 0.2: current_score += 10; reasons.append("✅ Mżawka")

        return min(max(current_score, 5), 100), day_status, reasons, wind_arrow, water_temp

# ======================================================
# 3. INTERFEJS MOBILNY
# ======================================================
class FishByteMobile(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Blue"
        self.engine = RealDataEngine()
        
        layout = MDBoxLayout(orientation='vertical', padding=20, spacing=15)
        self.city_input = MDTextField(hint_text="Wpisz miejscowość...", mode="rectangle", size_hint_y=None, height="60dp")
        layout.add_widget(self.city_input)
        
        btn_layout = MDBoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height="50dp")
        self.search_btn = MDRaisedButton(text="POBIERZ", size_hint_x=0.7, on_release=self.start_search)
        btn_layout.add_widget(self.search_btn)
        self.species_btn = MDRaisedButton(text="GATUNEK", size_hint_x=0.3, md_bg_color=(0.9, 0.5, 0.1, 1), on_release=self.show_species_dialog)
        btn_layout.add_widget(self.species_btn)
        layout.add_widget(btn_layout)

        self.scroll = MDScrollView()
        self.results_list = MDList()
        self.scroll.add_widget(self.results_list)
        layout.add_widget(self.scroll)
        return MDScreen(layout)

    def show_species_dialog(self, instance):
        items = list(self.engine.profiles.keys())
        MDDialog(title="Wybierz:", type="simple", items=[TwoLineAvatarIconListItem(text=s, on_release=lambda x, s=s: self.set_species(s)) for s in items]).open()

    def set_species(self, species):
        self.engine.set_species(species)
        self.species_btn.text = species.upper()
        if self.city_input.text: self.start_search(None)

    def start_search(self, instance):
        city = self.city_input.text
        if not city: return
        self.results_list.clear_widgets()
        self.results_list.add_widget(TwoLineAvatarIconListItem(text="Pobieranie...", secondary_text="Proszę czekać"))
        threading.Thread(target=self.worker, args=(city,)).start()

    def worker(self, city):
        loc = self.engine.get_location(city)
        if not loc: return
        data = self.engine.get_real_weather(loc['latitude'], loc['longitude'])
        if not data: return
        hourly = data['hourly']
        times = hourly['time']
        now = datetime.datetime.now().strftime("%Y-%m-%dT%H:00")
        try: start = times.index(now)
        except: start = 0
        results = []
        for i in range(start, start+24):
            if i>=len(times): break
            res = self.engine.analyze_data(hourly, i, loc['latitude'], loc['longitude'])
            dt = datetime.datetime.strptime(times[i], "%Y-%m-%dT%H:%M")
            results.append((dt,)+res)
        Clock.schedule_once(lambda x: self.update_ui(results, loc['name']))

    def update_ui(self, results, city_name):
        self.results_list.clear_widgets()
        self.city_input.hint_text = f"{city_name} ({self.engine.current_species})"
        for r in results:
            dt, score, status, reasons, wa, water_t = r
            icon = "fish" if score > 75 else "help-circle" if score > 40 else "close-circle"
            color = (0.2, 0.8, 0.4, 1) if score > 75 else (0.9, 0.8, 0.1, 1) if score > 40 else (0.9, 0.3, 0.3, 1)
            item = TwoLineAvatarIconListItem(text=f"{dt.strftime('%H:%M')} | {int(score)}% | Wiatr: {wa}", secondary_text=f"{status} | Woda: {water_t}°C", on_release=lambda x, rs=reasons: self.show_popup(rs))
            iw = IconLeftWidget(icon=icon)
            iw.theme_text_color = "Custom"
            iw.text_color = color
            item.add_widget(iw)
            self.results_list.add_widget(item)

    def show_popup(self, reasons):
        MDDialog(title="Szczegóły", text="\n".join(reasons)).open()

if __name__ == "__main__":
    FishByteMobile().run()