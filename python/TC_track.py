import os
import math
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from scipy.interpolate import PchipInterpolator
from shapely.geometry import Point
from shapely.ops import unary_union
from shapely.validation import make_valid

# 建立輸出目錄
os.makedirs('output/TC', exist_ok=True)

MACAU_LAT = 22.1595
MACAU_LON = 113.5685
KM_PER_DEG = 111.32

# 預報誤差圓錐預設半徑對應 (公里)
FORECAST_RADII_MAPPING = {
    0: 15,
    24: 100,
    48: 170,
    72: 255,
    96: 345,
    120: 465
}

TC_INTENSITY_TABLE = [
    {"max_wind": 40,    "name": "LPA",    "color": "#DDDFE2", "icon": "LPA.png"},
    {"max_wind": 62,    "name": "TD",     "color": "#6DD8FA", "icon": "TD.png"},
    {"max_wind": 87,    "name": "TS",     "color": "#9DD79C", "icon": "TS.png"},
    {"max_wind": 117,   "name": "STS",    "color": "#FFD363", "icon": "STS.png"},
    {"max_wind": 149,   "name": "TY",     "color": "#F78A31", "icon": "TY.png"},
    {"max_wind": 184,   "name": "STY",    "color": "#FF6F6F", "icon": "STY.png"},
    {"max_wind": 9999,  "name": "SuTY",   "color": "#DE82FF", "icon": "SuTY.png"}
]

def get_tc_style(wind_kmh):
    if wind_kmh in ["Ex", "EX"]:
        return "#DDDFE2", "Ex.png", "LPA"
    try:
        wind_val = float(wind_kmh)
    except (ValueError, TypeError):
        return "#DDDFE2", "LPA.png", "LPA"
    
    for rule in TC_INTENSITY_TABLE:
        if wind_val <= rule["max_wind"]:
            return rule["color"], rule["icon"], rule["name"]
    return TC_INTENSITY_TABLE[-1]["color"], TC_INTENSITY_TABLE[-1]["icon"], TC_INTENSITY_TABLE[-1]["name"]

def create_smooth_track_uniform_time(hours, lons, lats, time_step=1.0):
    if len(hours) < 2:
        return lons, lats, hours
    interp_hours = np.arange(hours[0], hours[-1] + 1e-5, time_step)
    smooth_lons = PchipInterpolator(hours, lons)(interp_hours)
    smooth_lats = PchipInterpolator(hours, lats)(interp_hours)
    return smooth_lons, smooth_lats, interp_hours

def parse_tc_csv(filepath):
    df = pd.read_csv(filepath)
    past_lats, past_lons, past_winds = [], [], []
    fcst_hours, fcst_lats, fcst_lons, fcst_winds, fcst_radii = [], [], [], [], []
    storm_name = ""

    for _, row in df.iterrows():
        cat = str(row['category']).strip().lower()
        lat = float(row['lat'])
        lon = float(row['lon'])
        wind = row['wind']
        name_val = row.get('name', '')
        if pd.notna(name_val) and str(name_val).strip() != '':
            storm_name = str(name_val).strip()

        if 'past' in cat or 'current' in cat:
            past_lats.append(lat)
            past_lons.append(lon)
            past_winds.append(wind)
        else:
            hr_str = ''.join(filter(str.isdigit, cat))
            hr = int(hr_str) if hr_str else 0
            fcst_hours.append(hr)
            fcst_lats.append(lat)
            fcst_lons.append(lon)
            fcst_winds.append(wind)
            fcst_radii.append(FORECAST_RADII_MAPPING.get(hr, 100 + hr * 3))

    return {
        "name": storm_name,
        "past": {"lats": np.array(past_lats), "lons": np.array(past_lons), "wind_kmh": past_winds},
        "forecast": {
            "hours": np.array(fcst_hours), 
            "lats": np.array(fcst_lats), 
            "lons": np.array(fcst_lons), 
            "wind_kmh": np.array(fcst_winds),
            "radii_km": fcst_radii
        }
    }

def generate_maps():
    files = ['A', 'B', 'C', 'D', 'E', 'F']
    valid_storms = {}

    for prefix in files:
        path = f'TCdata/{prefix}.csv'
        if os.path.exists(path):
            try:
                valid_storms[prefix] = parse_tc_csv(path)
            except Exception as e:
                print(f"解析 {path} 失敗: {e}")

    if not valid_storms:
        print("沒有找到任何有效的熱帶氣旋 CSV 資料。")
        return

    # 1. 產生綜合路徑圖 (all.png)
    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
    ax.set_extent([100, 160, 5, 50], crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.LAND, edgecolor="#959a9f", facecolor="#2d363f")
    ax.add_feature(cfeature.OCEAN, facecolor="#222a35")
    ax.add_feature(cfeature.BORDERS, linestyle=':', linewidth=0.25)

    for prefix, data in valid_storms.items():
        p = data["past"]
        if len(p["lats"]) > 0:
            sname = data["name"] if data["name"] else f"TC {prefix}"
            ax.plot(p["lons"], p["lats"], marker='o', label=sname, transform=ccrs.PlateCarree(), linewidth=1.5)
        f = data["forecast"]
        if len(f["lats"]) > 0:
            ax.plot(f["lons"], f["lats"], linestyle='--', marker='x', transform=ccrs.PlateCarree(), linewidth=1.2, alpha=0.8)

    ax.legend(loc='upper right', fontsize=9, facecolor='black', edgecolor='none', labelcolor='white')
    ax.gridlines(draw_labels=True, linewidth=0.3, color='gray', alpha=0.5, linestyle='--')
    plt.savefig('output/TC/all.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("已生成: output/TC/all.png")

    # 2. 逐一產生單一氣旋路徑圖與誤差圓錐 (A.png ~ F.png)
    for prefix, data in valid_storms.items():
        fig = plt.figure(figsize=(8, 8))
        ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
        
        p = data["past"]
        f = data["forecast"]
        has_forecast = len(f["hours"]) > 0

        # 計算誤差圓錐 (Error Cone Envelope)
        envelope_first = envelope_second_no_overlap = None
        if has_forecast:
            hours = f["hours"]
            lons = f["lons"]
            lats = f["lats"]
            radii_deg = np.array(f["radii_km"]) / KM_PER_DEG

            smooth_lons, smooth_lats, interp_hours = create_smooth_track_uniform_time(hours, lons, lats, time_step=1.0)
            smooth_radii = PchipInterpolator(hours, radii_deg)(interp_hours)

            circles_segment1 = [Point(smooth_lons[i], smooth_lats[i]).buffer(smooth_radii[i]) for i in range(len(smooth_lons)) if interp_hours[i] <= 72]
            circles_segment2 = [Point(smooth_lons[i], smooth_lats[i]).buffer(smooth_radii[i]) for i in range(len(smooth_lons)) if interp_hours[i] > 72]

            envelope_first = unary_union(circles_segment1) if circles_segment1 else None
            envelope_second = unary_union(circles_segment2) if circles_segment2 else None

            if len(interp_hours) > 0:
                idx_72h = int(np.argmin(np.abs(interp_hours - 72)))
                circle_72h_geom = Point(smooth_lons[idx_72h], smooth_lats[idx_72h]).buffer(smooth_radii[idx_72h])
                
                if envelope_second and not envelope_second.is_empty:
                    envelope_second = make_valid(envelope_second.difference(circle_72h_geom))
                if envelope_first and not envelope_first.is_empty and envelope_second and not envelope_second.is_empty:
                    envelope_second_no_overlap = make_valid(envelope_second.difference(envelope_first))
                else:
                    envelope_second_no_overlap = envelope_second

        # 設定地圖範圍
        all_lats = np.concatenate([p["lats"], f["lats"]]) if has_forecast and len(f["lats"]) > 0 else p["lats"]
        all_lons = np.concatenate([p["lons"], f["lons"]]) if has_forecast and len(f["lons"]) > 0 else p["lons"]
        
        if len(all_lats) > 0:
            lat_margin = max(3.0, (all_lats.max() - all_lats.min()) * 0.4)
            lon_margin = max(3.0, (all_lons.max() - all_lons.min()) * 0.4)
            ax.set_extent([all_lons.min() - lon_margin, all_lons.max() + lon_margin, 
                           all_lats.min() - lat_margin, all_lats.max() + lat_margin], crs=ccrs.PlateCarree())
        else:
            ax.set_extent([100, 160, 5, 50], crs=ccrs.PlateCarree())

        ax.add_feature(cfeature.LAND, edgecolor="#959a9f", facecolor="#2d363f")
        ax.add_feature(cfeature.OCEAN, facecolor="#222a35")
        ax.add_feature(cfeature.BORDERS, linestyle=':', linewidth=0.25)

        # 繪製誤差圓錐多邊形
        if has_forecast:
            if envelope_first and not envelope_first.is_empty:
                ax.add_geometries([envelope_first], crs=ccrs.PlateCarree(), facecolor='white', alpha=0.20)
            if envelope_second_no_overlap and not envelope_second_no_overlap.is_empty:
                ax.add_geometries([envelope_second_no_overlap], crs=ccrs.PlateCarree(), facecolor='white', alpha=0.10)

        # 繪製過去路徑與預報路徑
        if len(p["lats"]) > 0:
            ax.plot(p["lons"], p["lats"], color='white', marker='o', transform=ccrs.PlateCarree(), linewidth=2, label='Past Track')
        if has_forecast and len(f["lats"]) > 0:
            ax.plot(f["lons"], f["lats"], color='cyan', linestyle='--', marker='x', transform=ccrs.PlateCarree(), linewidth=1.5, label='Forecast')

        ax.gridlines(draw_labels=True, linewidth=0.3, color='gray', alpha=0.5, linestyle='--')
        title_str = f"{data['name']} ({prefix})" if data['name'] else f"Tropical Cyclone {prefix}"
        ax.set_title(title_str, color='white', fontsize=12)
        
        plt.savefig(f'output/TC/{prefix}.png', dpi=300, bbox_inches='tight')
        plt.close()
        print(f"已生成包含誤差圓錐的路徑圖: output/TC/{prefix}.png")

if __name__ == '__main__':
    generate_maps()
