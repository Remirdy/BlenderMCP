"""Gerçek Zamanlı Hava Durumu Işığı — OpenWeatherMap entegrasyonu."""
from __future__ import annotations

import os
import time
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..utils.http_utils import get_json
from ..utils.telemetry import record_tool
from ._common import call


WEATHER_API = "https://api.openweathermap.org/data/2.5/weather"


def _get_api_key() -> str | None:
    return os.environ.get("OPENWEATHERMAP_API_KEY")


def set_real_time_weather(
    location: str,
    time_of_day: str | None = None,   # "auto" | "day" | "sunset" | "night"
    intensity: float = 1.0,
) -> dict:
    """
    Gerçek zamanlı hava durumuna göre Blender sahnesinin aydınlatmasını ve ortamını ayarlar.

    - OpenWeatherMap'ten hava durumu, bulutluluk, sıcaklık çeker
    - Güneş pozisyonunu ve HDRI / world ayarlarını buna göre günceller
    - Terrain sahneleriyle özellikle güzel çalışır

    location: "Istanbul", "Kapadokya", "London" vb.
    time_of_day: "auto" (önerilen), "day", "sunset", "night"
    """
    api_key = _get_api_key()
    if not api_key:
        return {
            "ok": False,
            "error": "OPENWEATHERMAP_API_KEY environment variable tanımlı değil.",
            "hint": "OpenWeatherMap'ten ücretsiz API key al ve ayarla."
        }

    started = time.perf_counter()

    try:
        # 1. Hava durumu çek
        params = f"q={location}&appid={api_key}&units=metric"
        data = get_json(f"{WEATHER_API}?{params}", timeout=12)

        if "cod" in data and data["cod"] != 200:
            return {"ok": False, "error": f"Hava durumu alınamadı: {data.get('message')}"}

        weather = data.get("weather", [{}])[0]
        main = data.get("main", {})
        clouds = data.get("clouds", {}).get("all", 0)
        sys_info = data.get("sys", {})

        condition = weather.get("main", "Clear").lower()
        description = weather.get("description", "")
        temp = main.get("temp", 20)
        sunrise = sys_info.get("sunrise")
        sunset = sys_info.get("sunset")

        # 2. Karar mekanizması
        tod = (time_of_day or "auto").lower()
        if tod == "auto":
            now = int(time.time())
            if sunrise and sunset:
                if now < sunrise or now > sunset:
                    tod = "night"
                elif abs(now - sunset) < 3600 or abs(now - sunrise) < 3600:
                    tod = "sunset"
                else:
                    tod = "day"
            else:
                tod = "day"

        # 3. Blender'a ilet
        result = call("set_weather_environment", {
            "condition": condition,
            "description": description,
            "clouds": clouds,
            "temperature": temp,
            "time_of_day": tod,
            "intensity": intensity,
            "location": location,
        })

        record_tool("set_real_time_weather", (time.perf_counter() - started) * 1000, True)

        return {
            "ok": True,
            "location": location,
            "weather": {
                "condition": condition,
                "description": description,
                "clouds_percent": clouds,
                "temp_c": temp,
            },
            "time_of_day": tod,
            "blender_result": result,
        }

    except Exception as exc:
        record_tool("set_real_time_weather", (time.perf_counter() - started) * 1000, False, type(exc).__name__)
        return {"ok": False, "error": str(exc)}


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def _set_real_time_weather(location: str, time_of_day: str | None = None, intensity: float = 1.0) -> dict:
        return set_real_time_weather(location, time_of_day, intensity)
