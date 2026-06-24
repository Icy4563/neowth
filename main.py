import requests
from datetime import datetime
from kivy.clock import Clock
import time
from time import sleep as sleep_backup
from kivymd.app import MDApp
from kivy.lang import Builder
from kivy.core.text import LabelBase
import sys
from kivy.metrics import sp, dp
from datetime import date
import calendar
from kivy.storage.jsonstore import JsonStore
from kivy.core.window import Window
from typing import Optional, Tuple, List, Dict, Any, Union
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from kivymd.uix.button import MDButton, MDButtonText
from kivymd.uix.dialog import (
    MDDialog,
    MDDialogIcon,
    MDDialogHeadlineText,
    MDDialogSupportingText,
    MDDialogButtonContainer,
    MDDialogContentContainer,
)
from kivymd.uix.divider import MDDivider
from kivymd.uix.list import (
    MDListItem,
    MDListItemLeadingIcon,
    MDListItemSupportingText,
)
from kivymd.uix.textfield import MDTextField, MDTextFieldLeadingIcon, MDTextFieldHelperText
from kivy.uix.widget import Widget
from kivymd.uix.boxlayout import MDBoxLayout
from kivy.core.text import LabelBase
from kivy.properties import StringProperty
from kivy.uix.recycleview import RecycleView
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.navigationbar import MDNavigationBar, MDNavigationItem
from kivymd.uix.card import MDCard
import citysearch
from kivy.utils import platform
from timezonefinder import TimezoneFinderL
from kivy.core.text import LabelBase
from kivymd.uix.label import MDLabel


class VerticalRecycleView(RecycleView):
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        else:
            return False

    def on_touch_move(self, touch):
        if self.collide_point(*touch.pos):
            return super().on_touch_move(touch)
        else:
            return False

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            return super().on_touch_up(touch)
        else:
            return False


class RecycleViewBoxThing(BoxLayout):
    pass

class HorizontalRecycleView(RecycleView):
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        else:
            return False
        
    def on_touch_move(self, touch):
        if self.collide_point(*touch.pos):
            return super().on_touch_move(touch)
        else:
            return False
        
    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            return super().on_touch_up(touch)
        else:
            return False
        
storage = JsonStore("userOptions.json")

class RecycleViewBoxThing(BoxLayout):
    pass

#recognise the rootelement for navbar
class RootElement(MDBoxLayout):
    pass

#for the forecast view of that day
class ForecastWidget(MDBoxLayout):
    rain = StringProperty('')
    time = StringProperty('')
    icon = StringProperty('')
    temperature = StringProperty('')

class AnotherRecycleBoxThing(BoxLayout):
    pass

class CityListWidget(MDBoxLayout):
    city_name = StringProperty('')

_cache = {}
IP_API_URL = "http://ip-api.com/csv/?fields=34603472"
_MET_BASE = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
user_agent = None

has_location_changed = None

_tf = TimezoneFinderL()

# self.utilities
class utils():

    def database_to_timezone(self, coordinate_tuple: tuple):
        global _tf
        lat, lon = coordinate_tuple  # unpack coordinates (lat, lon order)

        # TimezoneFinderL uses (lat, lng)
        tz_name = _tf.timezone_at(lat=lat, lng=lon)

        if tz_name is None:
            raise ValueError("Could not determine timezone")

        return ZoneInfo(tz_name)

    def get_background(*args, current_icon):
        global show_graphics

        if show_graphics:
            if current_icon == "\ue430":
                return ("Graphics/sunny.png", 0.3)
            else:
                return ("Graphics/cloudy.png", 0.3)
        else:
            return ("Graphics/empty_graphic.png", 0)

    def _get_available_date_range(self, data: dict, tzinfo: ZoneInfo) -> Tuple[Optional[date], Optional[date]]:
        """
        Inspect the MET API JSON and return the earliest and latest available local dates.
        This helps validate requested day offsets.
        """
        ts_list = self._safe_get_in(data, ["properties", "timeseries"], [])
        if not ts_list:
            return None, None

        all_dates = []
        for ts in ts_list:
            ts_time = self._parse_iso8601(ts.get("time"))
            ts_local = ts_time.astimezone(tzinfo)
            all_dates.append(ts_local.date())

        if not all_dates:
            return None, None

        return min(all_dates), max(all_dates)


    def call_ip_api(self):
        try:
            response = requests.get(IP_API_URL, timeout=8)
            
        except requests.exceptions.ConnectionError:
            return (False, False, False, False, False)

        rawCSV = response.text

        continent, city, lat, lon, time_zone, time_offset = rawCSV.split(',')
        pCSV = (str(continent), str(city), float(lat), float(lon), str(time_zone), int(time_offset))

        continent, city, lat, lon, time_zone, time_offset = pCSV

        time_offset_in_hours = (time_offset / 3600)

        tuple = continent, city, lat, lon, time_zone
        return tuple

    def _parse_iso8601(self, s: str) -> datetime:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)

    def _safe_get_in(self, d: dict, path: List[str], default=None):
        x = d
        for p in path:
            if not isinstance(x, dict) or p not in x:
                return default
            x = x[p]
        return x

    def _nearest_timeseries(self, timeseries: List[dict], target_dt_utc: datetime) -> dict:
        best, best_diff = None, None
        for ts in timeseries:
            ts_time = self._parse_iso8601(ts.get("time"))
            diff = abs((ts_time - target_dt_utc).total_seconds())
            if best is None or diff < best_diff:
                best, best_diff = ts, diff
        return best

    def _extract_weather(self, entry: dict) -> dict:
        details = self._safe_get_in(entry, ["data", "instant", "details"], {})
        temp = details.get("air_temperature")
        wind = details.get("wind_speed")
        cloud = details.get("cloud_area_fraction")
        humidity = details.get("relative_humidity")
        rain = self._safe_get_in(entry, ["data", "next_1_hours", "details", "precipitation_amount"])
        if rain is None:
            rain = self._safe_get_in(entry, ["data", "next_6_hours", "details", "precipitation_amount"])
        if rain is None:
            rain = 0.0
        return {
            "time": entry.get("time"),
            "temperature_C": temp,
            "wind_speed_m_s": wind,
            "cloud_cover_percent": cloud,
            "rain_mm": rain,
            "relative_humidity_percent": humidity,
        }


    def get_nearest_current(
        self,
        lat: float,
        lon: float,
        target_time: Optional[datetime] = None,
        tz: str = "UTC",
        time_offset: Union[int, float, timedelta, None] = None,
        time_mode: str = "utc",
        user_agent: str = user_agent,
        altitude: Optional[int] = None,
    ) -> Dict[str, Any]:

        tzinfo = ZoneInfo(tz)
        if target_time is None:
            target_time = datetime.now(tzinfo if time_mode == "local" else ZoneInfo("UTC"))

        if time_offset:
            if isinstance(time_offset, (int, float)):
                target_time += timedelta(hours=float(time_offset))
            elif isinstance(time_offset, timedelta):
                target_time += time_offset

        if target_time.tzinfo is None:
            target_time = target_time.replace(tzinfo=tzinfo if time_mode == "local" else ZoneInfo("UTC"))
        if time_mode == "local":
            target_time = target_time.astimezone(ZoneInfo("UTC"))

        data = self._fetch_compact(lat, lon, user_agent, altitude)
        ts_list = self._safe_get_in(data, ["properties", "timeseries"], [])
        if not ts_list:
            raise ValueError("No timeseries data returned by MET API.")

        nearest = self._nearest_timeseries(ts_list, target_time)
        weather = self._extract_weather(nearest)
        weather["matched_time_utc"] = self._parse_iso8601(weather["time"]).isoformat()
        weather["matched_time_local"] = self._parse_iso8601(weather["time"]).astimezone(tzinfo).isoformat()
        weather["source_coordinates"] = (lat, lon)
        return weather

    def get_icon(self, rain_mm, cloud_cover):
        if cloud_cover < 75:
            # sunny
            icon = "\ue430"
        else:
            # cloudy
            icon = "\ue42d"

        if rain_mm > 1 and rain_mm < 5:
            icon = "\ue3a5"
        
        elif rain_mm >= 5:
            icon = "\ue3ea"

        return icon
    
    def __init__(self):
        self.weather_cache = {}

    def _fetch_compact(self, lat, lon, user_agent, altitude=None):
        lat = float(lat)
        lon = float(lon)
        cache_key = (lat, lon, altitude)

        if cache_key in self.weather_cache:
            return self.weather_cache[cache_key]

        headers = {"User-Agent": user_agent}
        params = {"lat": f"{lat:.6f}", "lon": f"{lon:.6f}"}
        if altitude is not None:
            params["altitude"] = str(int(altitude))

        resp = requests.get(_MET_BASE, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        self.weather_cache[cache_key] = data
        return data


    def hourly_forecast_for_day(
        self,
        lat: float,
        lon: float,
        day: Optional[date] = None,
        tz: str = "Etc/UTC",
        day_offset: Union[int, timedelta, None] = None,
        user_agent: str = user_agent,
        altitude: Optional[int] = None,
        full_output: bool = False,  # ✅ backward-compat flag
    ) -> Union[List[Tuple[str, Tuple[float, float, float, float, float]]], Dict[str, Any]]:
        global sync_time
        """
        Return hourly forecast for a specific day (or offset-day).
        If full_output=True, include metadata and range validation info.
        """

        tzinfo = ZoneInfo(tz)
        if day is None:
            day = datetime.now(tzinfo).date()

        data = self._fetch_compact(lat, lon, user_agent, altitude)
        min_date, max_date = self._get_available_date_range(data, tzinfo)

        if day_offset:
            if isinstance(day_offset, int):
                day += timedelta(days=day_offset)
            elif isinstance(day_offset, timedelta):
                day += day_offset

        # ✅ Validate available range
        if min_date and max_date and (day < min_date or day > max_date):
            empty_output = {
                "date_local": day.isoformat(),
                "hourly_data": [],
                "error": "Requested day_offset is out of available forecast range.",
                "available_date_range": (min_date.isoformat(), max_date.isoformat()),
                "source_coordinates": (lat, lon),
            }
            return empty_output if full_output else []

        ts_list = self._safe_get_in(data, ["properties", "timeseries"], [])
        result = []

        for ts in ts_list:
            ts_time = self._parse_iso8601(ts.get("time"))
            ts_local = ts_time.astimezone(tzinfo)

            # --- Robust timezone-safe rounding ---
            m = ts_local.minute

            if m >= 45:
                rounded = (ts_local + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            elif m >= 15:
                rounded = ts_local.replace(minute=30, second=0, microsecond=0)
            else:
                rounded = ts_local.replace(minute=0, second=0, microsecond=0)

            # Only top-of-hour timestamps are accepted
            if rounded.minute != 0:
                continue

            # For this local date?
            if rounded.date() == day:
                w = self._extract_weather(ts)
                result.append(
                    (
                        rounded.isoformat(),
                        (
                            w["temperature_C"],
                            w["wind_speed_m_s"],
                            w["cloud_cover_percent"],
                            w["rain_mm"],
                            w["relative_humidity_percent"],
                        ),
                    )
                )



        result.sort(key=lambda x: x[0])

        if full_output:
            return {
                "date_local": day.isoformat(),
                "hourly_data": result,
                "available_date_range": (min_date.isoformat(), max_date.isoformat()),
                "source_coordinates": (lat, lon),
            }

        # ✅ Legacy behavior (just list)

        sync_time = f"{time.localtime()[3]:02}:{time.localtime()[4]:02}"

        return result
    
class SurfaceWeatherNeoApp(MDApp):

    def graphics_handler(self, item, active):
        if active:
            if item.text == 'on':
                value = True
            elif item.text == 'off':
                value = False

            show_graphics = value
            storage.put("show_graphics", show_graphics=show_graphics)
            print(storage.get("show_graphics")["show_graphics"])

    def open_city_search_menu(*args):
        MDApp.get_running_app().root.ids.sm.transition.direction = 'down'
        MDApp.get_running_app().root.ids.sm.current = "CitySearchScreen"

    def theme_handler(self, instance):
        if instance.icon == "moon-waning-crescent":
            self.theme_cls.theme_style = "Dark"
            storage.put("theme", theme="Dark")
        else:
            self.theme_cls.theme_style = "Light"
            storage.put("theme", theme="Light")

    def navBarHandler(
        self,
        bar: MDNavigationBar,
        item: MDNavigationItem,
        item_icon: str,
        item_text: str,
    ):
        if item_text == "Current":
            call = "CurrentWeatherScreen"
            MDApp.get_running_app().root.ids.sm.transition.direction = 'right'
            MDApp.get_running_app().root.ids.sm.transition.speed = 3
        elif item_text == "Daily":
            call = "ForecastWeatherScreen"
            MDApp.get_running_app().root.ids.sm.transition.direction = 'left'
            MDApp.get_running_app().root.ids.sm.transition.speed = 3
        elif item_text == "Settings":
            call = "SettingsScreen"
            MDApp.get_running_app().root.ids.sm.transition.direction = 'left'
            MDApp.get_running_app().root.ids.sm.transition.speed = 3

        MDApp.get_running_app().root.ids.sm.current = call

    def city_has_been_selected(self, text):
        global has_location_changed
        text = text.replace("[ref=here]", "")
        text = text.replace("[/ref]", "")

        new_coordinates = citysearch.get_coordinates(city_name=text, partial=False)

        if len(new_coordinates) > 2:
            new_coordinates = new_coordinates[3], new_coordinates[4]

        timezone = str(utils().database_to_timezone(coordinate_tuple=new_coordinates))

        self.get_weather_screen_stuff(custom_ip=True, timezone=timezone, lon=new_coordinates[1], lat=new_coordinates[0], city=text, which_screen='current')
        self.get_weather_screen_stuff(custom_ip=True, timezone=timezone, lon=new_coordinates[1], lat=new_coordinates[0], city=text, which_screen='forecast', caller='city selector')
        has_location_changed = True
        MDApp.get_running_app().root.ids.sm.transition.direction = 'up'
        MDApp.get_running_app().root.ids.sm.current = "CurrentWeatherScreen"

    def show_cities(self, search_argument):
        search_argument = str(search_argument)

        data_for_city_list = []
        search_results = citysearch.find_city(partial=True, city_name=search_argument)[0]
        search_results = [sum_variable.get('city') for sum_variable in search_results]

        for f in range(len(search_results)):
            data_for_city_list.append({
                'city_name': f"[ref=here]{search_results[f]}[/ref]",
            })

        MDApp.get_running_app().root.ids.sm.get_screen("CitySearchScreen").ids.recycleviewpaneltwo.ids.inner_recycle_view.data = data_for_city_list

    def internet_error_popup_show(self, dt):
        self.full_popup = MDDialog(
            MDDialogHeadlineText(text="Network issue", font_style="ubuntu_display"),
            MDDialogSupportingText(
                text="Fetching the online weather and location data took too long.\n"
                     "Please double check your internet connection.\n\nPlease restart the app when you regain a connection",
                     font_style="ubuntu_title"
            ),
            auto_dismiss=False,
        )

        self.full_popup.open()

    def update_ui_regular_ip_current_screen(self):
        
        # avoid unnecessary calls to the IP API
        ip_cache = self.utilities.call_ip_api() 

        # quickly check if the user is having any connectivity problems
        if ip_cache[0] == False:
            Clock.schedule_once(self.internet_error_popup_show, 0)
            return

        # more weather caching for stability
        cacheuh = self.utilities.get_nearest_current(lat=ip_cache[2], lon=ip_cache[3], tz=ip_cache[4])

        # shorten Kivy ID calls
        id_short = MDApp.get_running_app().root.ids.sm

        # a bit of logic to get current data, and pass it to the current weather widgets
        current_temp = f"{cacheuh['temperature_C']}°"

        current_temp_alt = f"[b]{cacheuh['temperature_C']}°[/b]"

        current_wind = cacheuh['wind_speed_m_s']
        current_wind = current_wind * 3.6
        current_wind = round(current_wind)
        current_wind = str(current_wind)

        current_cloud = f"{round(cacheuh['cloud_cover_percent'])}%"
        current_humidity = f"{round(cacheuh['relative_humidity_percent'])}%"
        current_rain = cacheuh["rain_mm"]

        current_icon = str(self.utilities.get_icon(rain_mm=cacheuh['rain_mm'], cloud_cover=cacheuh['cloud_cover_percent']))

        id_short.get_screen("CurrentWeatherScreen").ids.temp_current.text = current_temp
        id_short.get_screen("CurrentWeatherScreen").ids.current_wind_speed.text = current_wind
        id_short.get_screen("CurrentWeatherScreen").ids.current_cloud.text = current_cloud
        id_short.get_screen("CurrentWeatherScreen").ids.current_humidity.text = current_humidity
        id_short.get_screen("CurrentWeatherScreen").ids.current_icon.text = current_icon

        id_short.get_screen("CurrentWeatherScreen").ids.background_image.source = self.utilities.get_background(current_icon=current_icon)[0]
        id_short.get_screen("CurrentWeatherScreen").ids.background_image.opacity = self.utilities.get_background(current_icon=current_icon)[1]

        id_short.get_screen("ForecastWeatherScreen").ids.background_image2.source = self.utilities.get_background(current_icon=current_icon)[0]
        id_short.get_screen("ForecastWeatherScreen").ids.background_image2.opacity = self.utilities.get_background(current_icon=current_icon)[1]

        id_short.get_screen("CurrentWeatherScreen").ids.location_text.text = f"[ref=here]{ip_cache[1]}[/ref]"
        id_short.get_screen("CurrentWeatherScreen").ids.current_rain_amount.text = f"{current_rain} mm"
        items = []

        # forecast for today
        re_view = MDApp.get_running_app().root.ids.sm.get_screen("CurrentWeatherScreen").ids.forecast_panel.ids.recycleviewpanel

            # Cache the whole weather of the day, mostly for shortning purposes since the hourly_forecast_for_dar() caches weather anyway
        long_weather_cache = self.utilities.hourly_forecast_for_day(lat=ip_cache[2], lon=ip_cache[3], tz=ip_cache[4])

        # bug fix for recycle-views (show data visibly)
        dim_sum = re_view.layout_manager
        dim_sum.bind(minimum_width=dim_sum.setter('width'))

        # fill in forecast for the day
        for i in range (1, 25):
            try:
                time = long_weather_cache[i][0]
                regular = datetime.fromisoformat(time)
                time = regular.strftime("%H:%M")
                cloud = long_weather_cache[i][1][2]

                temperature = long_weather_cache[i][1][0]

                rain = long_weather_cache[i][1][3]

                items.append({
                    'rain': f'{round(rain)} mm',
                    'time': f'{time}',
                    'icon': f'{self.utilities.get_icon(cloud_cover=cloud, rain_mm=rain)}',
                    'temperature': f'[b]{round(temperature)}°[/b]',
                })
            except Exception as e:
                print(e)
        # send organised data from the for loop to the recycle view
        re_view.data = items

            # Show last sync time on current weather page (and date)
        id_short.get_screen("CurrentWeatherScreen").ids.current_time_of_thy_synchronization.text = f"Last sync: {sync_time}"

        date = cacheuh['time']
        formater = datetime.fromisoformat(date)
        date = formater.date()
        date = date .strftime("%d %B %Y")
        id_short.get_screen("CurrentWeatherScreen").ids.current_date_time_of_thy_period_of_utlisation_in_thy_current_gregorian_calendar_year_such_as_but_only_for_example_two_thousand_and_twenty_five.text = f"{date}"
        
    def update_ui_custom_ip_current_screen(self, city:str, lat, lon, timezone):
        # avoid unnecessary calls to the IP API
        ip_cache = "very real continent guys", city, lat, lon, timezone

        cacheuhhh = utils().get_nearest_current(lat=ip_cache[2], lon=ip_cache[3], tz=ip_cache[4])

    # shorten Kivy ID calls
        id_short = MDApp.get_running_app().root.ids.sm

        # a bit of logic to get current data, and pass it to the current weather widgets
        current_temp = f"[b]{cacheuhhh['temperature_C']}°[/b]"
        current_wind = cacheuhhh['wind_speed_m_s']
        current_wind = current_wind * 3.6
        current_wind = round(current_wind)
        current_wind = str(current_wind)

        current_cloud = f"{round(cacheuhhh['cloud_cover_percent'])}%"
        current_humidity = f"{round(cacheuhhh['relative_humidity_percent'])}%"
        current_rain = cacheuhhh["rain_mm"]

        current_icon = str(self.utilities.get_icon(rain_mm=cacheuhhh['rain_mm'], cloud_cover=cacheuhhh['cloud_cover_percent']))

        id_short.get_screen("CurrentWeatherScreen").ids.temp_current.text = current_temp
        id_short.get_screen("CurrentWeatherScreen").ids.current_wind_speed.text = current_wind
        id_short.get_screen("CurrentWeatherScreen").ids.current_cloud.text = current_cloud
        id_short.get_screen("CurrentWeatherScreen").ids.current_humidity.text = current_humidity
        id_short.get_screen("CurrentWeatherScreen").ids.current_icon.text = current_icon

        id_short.get_screen("CurrentWeatherScreen").ids.background_image.source = self.utilities.get_background(current_icon=current_icon)[0]
        id_short.get_screen("CurrentWeatherScreen").ids.background_image.opacity = self.utilities.get_background(current_icon=current_icon)[1]

        id_short.get_screen("ForecastWeatherScreen").ids.background_image2.source = self.utilities.get_background(current_icon=current_icon)[0]
        id_short.get_screen("ForecastWeatherScreen").ids.background_image2.opacity = self.utilities.get_background(current_icon=current_icon)[1]

        id_short.get_screen("CurrentWeatherScreen").ids.location_text.text = f"[ref=here]{ip_cache[1]}[/ref]"
        id_short.get_screen("CurrentWeatherScreen").ids.current_rain_amount.text = f"{current_rain} mm"
        items = []

        # forecast for today
        re_view = MDApp.get_running_app().root.ids.sm.get_screen("CurrentWeatherScreen").ids.forecast_panel.ids.recycleviewpanel

            # Cache the whole weather of the day, mostly for shortning purposes since the hourly_forecast_for_dar() caches weather anyway
        long_weather_cache = self.utilities.hourly_forecast_for_day(lat=ip_cache[2], lon=ip_cache[3], tz=ip_cache[4])

        # bug fix for recycle-views (show data visibly)
        dim_sum = re_view.layout_manager
        dim_sum.bind(minimum_width=dim_sum.setter('width'))

        # fill in forecast for the day
        for i in range (1, 25):
            try:
                time = long_weather_cache[i][0]
                regular = datetime.fromisoformat(time)
                time = regular.strftime("%H:%M")
                cloud = long_weather_cache[i][1][2]

                temperature = long_weather_cache[i][1][0]

                rain = long_weather_cache[i][1][3]

                items.append({
                    'rain': f'{round(rain)} mm',
                    'time': f'{time}',
                    'icon': f'{self.utilities.get_icon(cloud_cover=cloud, rain_mm=rain)}',
                    'temperature': f'[b]{round(temperature)}°[/b]',
                })
            except Exception as e:
                print(e)
        # send organised data from the for loop to the recycle view
        re_view.data = items

            # Show last sync time on current weather page (and date)
        id_short.get_screen("CurrentWeatherScreen").ids.current_time_of_thy_synchronization.text = f"Last sync: {sync_time}"

        date = cacheuhhh['time']
        formater = datetime.fromisoformat(date)
        date = formater.date()
        date = date .strftime("%d %B %Y")
        id_short.get_screen("CurrentWeatherScreen").ids.current_date_time_of_thy_period_of_utlisation_in_thy_current_gregorian_calendar_year_such_as_but_only_for_example_two_thousand_and_twenty_five.text = f"{date}"

    def update_ui_regular_ip_forecast_screen(self):
        
        # avoid unnecessary calls to the IP API
        ip_cache = self.utilities.call_ip_api() 

        # more weather caching for stability
        cacheuh = self.utilities.get_nearest_current(lat=ip_cache[2], lon=ip_cache[3], tz=ip_cache[4])

        current_temp = f"{cacheuh['temperature_C']}°"

        # shorten Kivy ID calls
        id_short = MDApp.get_running_app().root.ids.sm

        # forecast for tomorrow
        re_view2 = MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_forecast.ids.recycleviewpanel

        re_view3 = MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_one_forecast.ids.recycleviewpanel
        re_view4 = MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_two_forecast.ids.recycleviewpanel
        re_view5 = MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_three_forecast.ids.recycleviewpanel
        re_view6 = MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_four_forecast.ids.recycleviewpanel
        re_view7 = MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_five_forecast.ids.recycleviewpanel
        current_icon = str(self.utilities.get_icon(rain_mm=cacheuh['rain_mm'], cloud_cover=cacheuh['cloud_cover_percent']))

        dim_sum2 = re_view2.layout_manager
        dim_sum2.bind(minimum_width=dim_sum2.setter('width'))

        dim_sum3 = re_view3.layout_manager
        dim_sum3.bind(minimum_width=dim_sum3.setter('width'))

        dim_sum4 = re_view4.layout_manager
        dim_sum4.bind(minimum_width=dim_sum4.setter('width'))

        dim_sum5 = re_view5.layout_manager
        dim_sum5.bind(minimum_width=dim_sum5.setter('width'))

        dim_sum6 = re_view6.layout_manager
        dim_sum6.bind(minimum_width=dim_sum6.setter('width'))

        dim_sum7 = re_view7.layout_manager
        dim_sum7.bind(minimum_width=dim_sum7.setter('width'))

        items2 = []
        items3 = []
        items4 = []
        items5 = []
        items6 = []
        items7 = []

        g_index = {1: 6, 2: 8, 3: 10, 4: 12, 5: 14, 6: 16, 7: 18, 9: 20, 10: 22}
        tmr_cache = self.utilities.hourly_forecast_for_day(day_offset=1, full_output=False, lat = ip_cache[2], lon=ip_cache[3], tz=ip_cache[4])
        for g in range(1, 11):
            try:
                a = g_index[g]

                rain_tmr = tmr_cache[a][1][3]
                temperature_tmr = tmr_cache[a][1][0]
                time_tmr = tmr_cache[a][0]
                regular_tmr = datetime.fromisoformat(time_tmr)
                time_tmr = regular_tmr.strftime("%H:%M")
                cloud_tmr = tmr_cache[a][1][2]
                tmr_icon = self.utilities.get_icon(cloud_cover=cloud_tmr, rain_mm=rain_tmr)
                items2.append({
                    'rain': f'{round(rain_tmr)} mm',
                    'time': f'{time_tmr}',
                    'icon': f'{tmr_icon}',
                    'temperature': f'{temperature_tmr}°',
                })
            except Exception as e:
                # print("forecast loop", e)
                pass

        a = None

        re_view2.data = items2
        try:
            MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_date.text = f"{regular_tmr.strftime('%d-%m')}"
        except:
            MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.card0.opacity = 0.45

        a_index = {1: 6, 2: 8, 3: 10, 4: 12, 5: 14, 6: 16, 7: 18, 9: 20, 10: 22}
        tmr_one_cache = self.utilities.hourly_forecast_for_day(day_offset=2, full_output=False, lat = ip_cache[2], lon=ip_cache[3])
        for n in range(1, 11):
            try:
                # scale increments to pre-set sections of the day
                a = a_index[n]

                rain_tmr_one = tmr_one_cache[a][1][3]
                temperature_tmr_one= tmr_one_cache[a][1][0]
                time_tmr_one = tmr_one_cache[a][0]
                regular_tmr_one = datetime.fromisoformat(time_tmr_one)
                time_tmr_one = regular_tmr_one.strftime("%H:%M")
                cloud_tmr_one = tmr_one_cache[a][1][2]
                tmr_one_icon = self.utilities.get_icon(cloud_cover=cloud_tmr_one, rain_mm=rain_tmr_one)
                items3.append({
                    'rain': f'{round(rain_tmr_one)} mm',
                    'time': f'{time_tmr_one}',
                    'icon': f'{tmr_one_icon}',
                    'temperature': f'{temperature_tmr_one}°',
                })
            except Exception as e:
                print("forecast loop", e)

        re_view3.data = items3
        try:
            MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_one_date.text = f"{regular_tmr_one.strftime('%d-%m')}"
        except:
            MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.card1.opacity = 0.2

        b_index = {1: 1, 2: 2, 3: 3, 4: 4}
        tmr_two_cache = self.utilities.hourly_forecast_for_day(day_offset=3, full_output=False, lat = ip_cache[2], lon=ip_cache[3])
        for i in range(1, 5):
            try:
                # scale increments to pre-set sections of the day
                b = b_index[i]

                rain_tmr_two = tmr_two_cache[b][1][3]
                temperature_tmr_two= tmr_two_cache[b][1][0]
                time_tmr_two = tmr_two_cache[b][0]
                regular_tmr_two = datetime.fromisoformat(time_tmr_two)
                time_tmr_two = regular_tmr_two.strftime("%H:%M")
                cloud_tmr_two = tmr_two_cache[b][1][2]
                tmr_two_icon = self.utilities.get_icon(cloud_cover=cloud_tmr_two, rain_mm=rain_tmr_two)
                items4.append({
                    'rain': f'{round(rain_tmr_two)} mm',
                    'time': f'{time_tmr_two}',
                    'icon': f'{tmr_two_icon}',
                    'temperature': f'{temperature_tmr_two}°',
                })
            except Exception as e:
                print("forecast loop 2", e)

        re_view4.data = items4
        try:
            MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_two_date.text = f"{regular_tmr_two.strftime('%d-%m')}"
        except:
            MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.card2.opacity = 0.2

        f_index = {1: 1, 2: 2, 3: 3, 4: 4}
        tmr_three_cache = self.utilities.hourly_forecast_for_day(day_offset=4, full_output=False, lat = ip_cache[2], lon=ip_cache[3])
        for h in range(1, 5):
            try:
                # scale increments to pre-set sections of the day
                f = f_index[h]

                rain_tmr_three = tmr_three_cache[f][1][3]
                temperature_tmr_three= tmr_three_cache[f][1][0]
                time_tmr_three = tmr_three_cache[f][0]
                regular_tmr_three = datetime.fromisoformat(time_tmr_three)
                time_tmr_three = regular_tmr_three.strftime("%H:%M")
                cloud_tmr_three = tmr_three_cache[f][1][2]
                tmr_three_icon = self.utilities.get_icon(cloud_cover=cloud_tmr_three, rain_mm=rain_tmr_three)
                items5.append({
                    'rain': f'{round(rain_tmr_three)} mm',
                    'time': f'{time_tmr_three}',
                    'icon': f'{tmr_three_icon}',
                    'temperature': f'{temperature_tmr_three}°',
                })
            except Exception as e:
                print("forecast loop 2", e)

            re_view5.data = items5
            try:
                MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_three_date.text = f"{regular_tmr_three.strftime('%d-%m')}"
            except:
                MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.card3.opacity = 0.2

        p_index = {1: 1, 2: 2, 3: 3, 4: 4}
        tmr_four_cache = self.utilities.hourly_forecast_for_day(day_offset=5, full_output=False, lat = ip_cache[2], lon=ip_cache[3])
        for j in range(1, 5):
            try:
                # scale increments to pre-set sections of the day
                p = p_index[j]

                rain_tmr_four = tmr_four_cache[p][1][3]
                temperature_tmr_four= tmr_four_cache[p][1][0]
                time_tmr_four = tmr_four_cache[p][0]
                regular_tmr_four = datetime.fromisoformat(time_tmr_four)
                time_tmr_four = regular_tmr_four.strftime("%H:%M")
                cloud_tmr_four = tmr_four_cache[p][1][2]
                tmr_four_icon = self.utilities.get_icon(cloud_cover=cloud_tmr_four, rain_mm=rain_tmr_four)
                items6.append({
                    'rain': f'{round(rain_tmr_four)} mm',
                    'time': f'{time_tmr_four}',
                    'icon': f'{tmr_four_icon}',
                    'temperature': f'{temperature_tmr_four}°',
                })
            except Exception as e:
                print("forecast loop 2", e)

        re_view6.data = items6
        try:
            MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_four_date.text = f"{regular_tmr_four.strftime('%d-%m')}"
        except:
            MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.card4.opacity = 0.2

        d_index = {1: 1, 2: 2, 3: 3, 4: 4}
        tmr_five_cache = self.utilities.hourly_forecast_for_day(day_offset=6, full_output=False, lat = ip_cache[2], lon=ip_cache[3])
        for w in range(1, 5):
            try:
                # scale increments to pre-set sections of the day
                d = d_index[w]

                rain_tmr_five = tmr_five_cache[d][1][3]
                temperature_tmr_five = tmr_five_cache[d][1][0]
                time_tmr_five = tmr_five_cache[d][0]
                regular_tmr_five = datetime.fromisoformat(time_tmr_five)
                time_tmr_five = regular_tmr_five.strftime("%H:%M")
                cloud_tmr_five = tmr_five_cache[d][1][2]
                tmr_five_icon = self.utilities.get_icon(cloud_cover=cloud_tmr_five, rain_mm=rain_tmr_five)
                items7.append({
                    'rain': f'{round(rain_tmr_five)} mm',
                    'time': f'{time_tmr_five}',
                    'icon': f'{tmr_five_icon}',
                    'temperature': f'{temperature_tmr_five}°',
                })
            except Exception as e:
                print("forecast loop 2", e)

        re_view7.data = items7
        try:
            MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_five_date.text = f"{regular_tmr_five.strftime('%d-%m')}"
        except:
            MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.card5.opacity = 0.2

    # =============================================================================================================================================
    # =============================================================================================================================================

        # Show the last sync time on the daily forecast page
        id_short.get_screen("ForecastWeatherScreen").ids.current_icon.text = current_icon
        id_short.get_screen("ForecastWeatherScreen").ids.temp_current.text = current_temp
        id_short.get_screen("ForecastWeatherScreen").ids.sync_time.text = f"Last sync: {sync_time}"

    def update_ui_custom_ip_forecast_screen(self, city:str, lat, lon, timezone):
        self.forecast_rendered = True

        ip_cache = "very real continent guys", city, lat, lon, timezone

        # more weather caching for stability
        cacheuhhh = self.utilities.get_nearest_current(lat=ip_cache[2], lon=ip_cache[3], tz=ip_cache[4])

        current_temp = f"{cacheuhhh['temperature_C']}°"

        # shorten Kivy ID calls
        id_short = MDApp.get_running_app().root.ids.sm

        # forecast for tomorrow
        re_view2 = MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_forecast.ids.recycleviewpanel

        re_view3 = MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_one_forecast.ids.recycleviewpanel
        re_view4 = MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_two_forecast.ids.recycleviewpanel
        re_view5 = MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_three_forecast.ids.recycleviewpanel
        re_view6 = MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_four_forecast.ids.recycleviewpanel
        re_view7 = MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_five_forecast.ids.recycleviewpanel
        current_icon = str(self.utilities.get_icon(rain_mm=cacheuhhh['rain_mm'], cloud_cover=cacheuhhh['cloud_cover_percent']))

        dim_sum2 = re_view2.layout_manager
        dim_sum2.bind(minimum_width=dim_sum2.setter('width'))

        dim_sum3 = re_view3.layout_manager
        dim_sum3.bind(minimum_width=dim_sum3.setter('width'))

        dim_sum4 = re_view4.layout_manager
        dim_sum4.bind(minimum_width=dim_sum4.setter('width'))

        dim_sum5 = re_view5.layout_manager
        dim_sum5.bind(minimum_width=dim_sum5.setter('width'))

        dim_sum6 = re_view6.layout_manager
        dim_sum6.bind(minimum_width=dim_sum6.setter('width'))

        dim_sum7 = re_view7.layout_manager
        dim_sum7.bind(minimum_width=dim_sum7.setter('width'))

        items2 = []
        items3 = []
        items4 = []
        items5 = []
        items6 = []
        items7 = []

        g_index = {1: 6, 2: 8, 3: 10, 4: 12, 5: 14, 6: 16, 7: 18, 9: 20, 10: 22}
        tmr_cache = self.utilities.hourly_forecast_for_day(day_offset=1, full_output=False, lat = ip_cache[2], lon=ip_cache[3], tz=ip_cache[4])
        for g in range(1, 11):
            try:
                a = g_index[g]

                rain_tmr = tmr_cache[a][1][3]
                temperature_tmr = tmr_cache[a][1][0]
                time_tmr = tmr_cache[a][0]
                regular_tmr = datetime.fromisoformat(time_tmr)
                time_tmr = regular_tmr.strftime("%H:%M")
                cloud_tmr = tmr_cache[a][1][2]
                tmr_icon = self.utilities.get_icon(cloud_cover=cloud_tmr, rain_mm=rain_tmr)
                items2.append({
                    'rain': f'{round(rain_tmr)} mm',
                    'time': f'{time_tmr}',
                    'icon': f'{tmr_icon}',
                    'temperature': f'{temperature_tmr}°',
                })
            except Exception as e:
                # print("forecast loop", e)
                pass

        a = None

        re_view2.data = items2
        try:
            MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_date.text = f"{regular_tmr.strftime('%d-%m')}"
        except:
            MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.card0.opacity = 0.45

        a_index = {1: 6, 2: 8, 3: 10, 4: 12, 5: 14, 6: 16, 7: 18, 9: 20, 10: 22}
        tmr_one_cache = self.utilities.hourly_forecast_for_day(day_offset=2, full_output=False, lat = ip_cache[2], lon=ip_cache[3])
        for n in range(1, 11):
            try:
                # scale increments to pre-set sections of the day
                a = a_index[n]

                rain_tmr_one = tmr_one_cache[a][1][3]
                temperature_tmr_one= tmr_one_cache[a][1][0]
                time_tmr_one = tmr_one_cache[a][0]
                regular_tmr_one = datetime.fromisoformat(time_tmr_one)
                time_tmr_one = regular_tmr_one.strftime("%H:%M")
                cloud_tmr_one = tmr_one_cache[a][1][2]
                tmr_one_icon = self.utilities.get_icon(cloud_cover=cloud_tmr_one, rain_mm=rain_tmr_one)
                items3.append({
                    'rain': f'{round(rain_tmr_one)} mm',
                    'time': f'{time_tmr_one}',
                    'icon': f'{tmr_one_icon}',
                    'temperature': f'{temperature_tmr_one}°',
                })
            except Exception as e:
                print("forecast loop", e)

        re_view3.data = items3
        try:
            MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_one_date.text = f"{regular_tmr_one.strftime('%d-%m')}"
        except:
            MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.card1.opacity = 0.2

        b_index = {1: 1, 2: 2, 3: 3, 4: 4}
        tmr_two_cache = self.utilities.hourly_forecast_for_day(day_offset=3, full_output=False, lat = ip_cache[2], lon=ip_cache[3])
        for i in range(1, 5):
            try:
                # scale increments to pre-set sections of the day
                b = b_index[i]

                rain_tmr_two = tmr_two_cache[b][1][3]
                temperature_tmr_two= tmr_two_cache[b][1][0]
                time_tmr_two = tmr_two_cache[b][0]
                regular_tmr_two = datetime.fromisoformat(time_tmr_two)
                time_tmr_two = regular_tmr_two.strftime("%H:%M")
                cloud_tmr_two = tmr_two_cache[b][1][2]
                tmr_two_icon = self.utilities.get_icon(cloud_cover=cloud_tmr_two, rain_mm=rain_tmr_two)
                items4.append({
                    'rain': f'{round(rain_tmr_two)} mm',
                    'time': f'{time_tmr_two}',
                    'icon': f'{tmr_two_icon}',
                    'temperature': f'{temperature_tmr_two}°',
                })
            except Exception as e:
                print("forecast loop 2", e)

        re_view4.data = items4
        try:
            MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_two_date.text = f"{regular_tmr_two.strftime('%d-%m')}"
        except:
            MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.card2.opacity = 0.2

        f_index = {1: 1, 2: 2, 3: 3, 4: 4}
        tmr_three_cache = self.utilities.hourly_forecast_for_day(day_offset=4, full_output=False, lat = ip_cache[2], lon=ip_cache[3])
        for h in range(1, 5):
            try:
                # scale increments to pre-set sections of the day
                f = f_index[h]

                rain_tmr_three = tmr_three_cache[f][1][3]
                temperature_tmr_three= tmr_three_cache[f][1][0]
                time_tmr_three = tmr_three_cache[f][0]
                regular_tmr_three = datetime.fromisoformat(time_tmr_three)
                time_tmr_three = regular_tmr_three.strftime("%H:%M")
                cloud_tmr_three = tmr_three_cache[f][1][2]
                tmr_three_icon = self.utilities.get_icon(cloud_cover=cloud_tmr_three, rain_mm=rain_tmr_three)
                items5.append({
                    'rain': f'{round(rain_tmr_three)} mm',
                    'time': f'{time_tmr_three}',
                    'icon': f'{tmr_three_icon}',
                    'temperature': f'{temperature_tmr_three}°',
                })
            except Exception as e:
                print("forecast loop 2", e)

            re_view5.data = items5
            try:
                MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_three_date.text = f"{regular_tmr_three.strftime('%d-%m')}"
            except:
                MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.card3.opacity = 0.2

        p_index = {1: 1, 2: 2, 3: 3, 4: 4}
        tmr_four_cache = self.utilities.hourly_forecast_for_day(day_offset=5, full_output=False, lat = ip_cache[2], lon=ip_cache[3])
        for j in range(1, 5):
            try:
                # scale increments to pre-set sections of the day
                p = p_index[j]

                rain_tmr_four = tmr_four_cache[p][1][3]
                temperature_tmr_four= tmr_four_cache[p][1][0]
                time_tmr_four = tmr_four_cache[p][0]
                regular_tmr_four = datetime.fromisoformat(time_tmr_four)
                time_tmr_four = regular_tmr_four.strftime("%H:%M")
                cloud_tmr_four = tmr_four_cache[p][1][2]
                tmr_four_icon = self.utilities.get_icon(cloud_cover=cloud_tmr_four, rain_mm=rain_tmr_four)
                items6.append({
                    'rain': f'{round(rain_tmr_four)} mm',
                    'time': f'{time_tmr_four}',
                    'icon': f'{tmr_four_icon}',
                    'temperature': f'{temperature_tmr_four}°',
                })
            except Exception as e:
                print("forecast loop 2", e)

        re_view6.data = items6
        try:
            MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_four_date.text = f"{regular_tmr_four.strftime('%d-%m')}"
        except:
            MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.card4.opacity = 0.2

        d_index = {1: 1, 2: 2, 3: 3, 4: 4}
        tmr_five_cache = self.utilities.hourly_forecast_for_day(day_offset=6, full_output=False, lat = ip_cache[2], lon=ip_cache[3])
        for w in range(1, 5):
            try:
                # scale increments to pre-set sections of the day
                d = d_index[w]

                rain_tmr_five = tmr_five_cache[d][1][3]
                temperature_tmr_five = tmr_five_cache[d][1][0]
                time_tmr_five = tmr_five_cache[d][0]
                regular_tmr_five = datetime.fromisoformat(time_tmr_five)
                time_tmr_five = regular_tmr_five.strftime("%H:%M")
                cloud_tmr_five = tmr_five_cache[d][1][2]
                tmr_five_icon = self.utilities.get_icon(cloud_cover=cloud_tmr_five, rain_mm=rain_tmr_five)
                items7.append({
                    'rain': f'{round(rain_tmr_five)} mm',
                    'time': f'{time_tmr_five}',
                    'icon': f'{tmr_five_icon}',
                    'temperature': f'{temperature_tmr_five}°',
                })
            except Exception as e:
                print("forecast loop 2", e)

        re_view7.data = items7
        try:
            MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.tmr_five_date.text = f"{regular_tmr_five.strftime('%d-%m')}"
        except:
            MDApp.get_running_app().root.ids.sm.get_screen("ForecastWeatherScreen").ids.card5.opacity = 0.2


# =============================================================================================================================================
# =============================================================================================================================================

        # Show the last sync time on the daily forecast page
        id_short.get_screen("ForecastWeatherScreen").ids.current_icon.text = current_icon
        id_short.get_screen("ForecastWeatherScreen").ids.temp_current.text = current_temp
        id_short.get_screen("ForecastWeatherScreen").ids.sync_time.text = f"Last sync: {sync_time}"

    def get_weather_screen_stuff(self, lon = None, timezone = None, custom_ip=False, city:str = None, lat:int = None, which_screen:str = None, caller:str = None):
        
        
        if not custom_ip:
            if which_screen == 'current':
                self.forecast_rendered = False

                self.update_ui_regular_ip_current_screen()

            # ================================================================================================
            if which_screen == 'forecast' and not self.forecast_rendered:
                self.forecast_rendered = True

                self.update_ui_regular_ip_forecast_screen()

            else:
                pass
                
        # custom ip / location
        else:
            if which_screen == 'current':
                self.forecast_rendered = False

                self.update_ui_custom_ip_current_screen(city=city, lat=lat, lon=lon, timezone=timezone)      

            if which_screen == 'forecast' and not self.forecast_rendered and caller == 'city selector':
                self.update_ui_custom_ip_forecast_screen(city=city, lat=lat, lon=lon, timezone=timezone)
            else:
                pass
        

    def on_start(self):
        if self.ready_to_render:
            self.get_weather_screen_stuff(which_screen='current')
        else:
            pass

    # creating the popup that pops-up when no email is saved
    def show_email_popup(self):

        popup_box_layout = MDBoxLayout(
            orientation = 'vertical',
            adaptive_height = True,
            padding=("18dp", "18dp"),
            spacing="18dp",
        )

        popup_box_layout.add_widget(MDDivider())

        self.email_field = MDTextField(
                    MDTextFieldLeadingIcon(
                        icon="email",
                    ),
                    MDTextFieldHelperText(
                        text="Please enter your email",
                        mode="persistent",
                    ),
                    mode="filled",
                    size_hint = (0.8, 0.2),
                    pos_hint = {'center_x': 0.5},
                    id = "email_input_box")

        popup_box_layout.add_widget(self.email_field)

        def save_email(*args):
            text = self.email_field.text
            if text:
                storage.put("email", email=text)
                dialog.dismiss()
            else:
                pass

        dialog = MDDialog(
            MDDialogHeadlineText(text="Email input",),
            MDDialogSupportingText(text="Please enter your email. This is necessary to call the weather API."
                                   " Please keep in mind that the app does not check if the email is valid "
                                   "if you have entered your email wrong, you may experience bugs or may even be banned "
                                   "from the weather service "
                                   "To change your email, please uninstall and reinstall the app",),
            MDDialogContentContainer(
                popup_box_layout,
            ),
            MDDialogButtonContainer(
                Widget(),
                MDButton(
                    MDButtonText(text="Ok"),
                    style="text",
                    on_release = save_email
                ),
            ),
        auto_dismiss=False,)

        dialog.open()

    def build(self):
        global user_agent, show_graphics

        LabelBase.register(name="ubuntu_title", fn_regular="Graphics/Fonts/Ubuntu-Regular.ttf")

        self.theme_cls.font_styles["ubuntu_title"] = {
            "large": {
                "line-height": 1.1,
                "font-name": "ubuntu_title",
                "font-size": sp(24),
            },
            "medium": {
                "line-height": 1.1,
                "font-name": "ubuntu_title",
                "font-size": sp(17),
            },
            "small": {
                "line-height": 1.1,
                "font-name": "ubuntu_title",
                "font-size": sp(15),
            }
        }

        LabelBase.register(name="ubuntu_display", fn_regular="Graphics/Fonts/Ubuntu-Regular.ttf")

        self.theme_cls.font_styles["ubuntu_display"] = {
            "large": {
            "line-height": 1.1,
            "font-name": "ubuntu_display",
            "font-size": sp(57),
            },
            "medium": {
                "line-height": 1.1,
                "font-name": "ubuntu_display",
                "font-size": sp(45),
            },
            "small": {
                "line-height": 1.1,
                "font-name": "ubuntu_display",
                "font-size": sp(36),
            }
        }

        LabelBase.register(name="ubuntu_title_bold", fn_regular="Graphics/Fonts/Ubuntu-Bold.ttf")

        self.theme_cls.font_styles["ubuntu_title_bold"] = {
            "large": {
                "line-height": 1.1,
                "font-name": "ubuntu_title_bold",
                "font-size": sp(57),
            },
            "medium": {
                "line-height": 1.1,
                "font-name": "ubuntu_title_bold",
                "font-size": sp(45),
            },
            "small": {
                "line-height": 1.1,
                "font-name": "ubuntu_title_bold",
                "font-size": sp(36),
            }
        }

        self.utilities = utils()

        #import fonts and icon fonts
        LabelBase.register(name='Material-Icons', fn_regular='Graphics/MaterialIcons.ttf')

        if storage.exists("theme"):
            theme = storage.get("theme")["theme"]
            self.theme_cls.theme_style = theme
            self.theme_cls.primary_palette = "Olive"
        
        else:
            self.theme_cls.theme_style = "Light"

        if storage.exists("show_graphics"):
            show_graphics = storage.get("show_graphics")["show_graphics"]
        else:
            show_graphics = True

        if storage.exists('email'):
            email = storage.get("email")["email"]
            user_agent = f"surface-weather-neo/1.0 {email}"
            self.ready_to_render = True
            return Builder.load_file("surface-weather-neo.kv")
        else:
            self.show_email_popup()
            self.ready_to_render = False

SurfaceWeatherNeoApp().run()