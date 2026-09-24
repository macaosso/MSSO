import os
import math
import platform
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import matplotlib.font_manager as fm
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from scipy.interpolate import PchipInterpolator
from shapely.geometry import Point, LineString, box
from shapely.ops import unary_union
from shapely.validation import make_valid

# 建立輸出與圖示目錄
os.makedirs('output/TC', exist_ok=True)
os.makedirs('TCdata', exist_ok=True)
os.makedirs('icon/tc_icon', exist_ok=True)
os.makedirs('icon/MSSO_icon', exist_ok=True)

# 執行 Python 程式碼前，先清空 output/TC 資料夾底下的所有舊檔案
for file in os.listdir('output/TC'):
    file_path = os.path.join('output/TC', file)
    if os.path.isfile(file_path):
        os.remove(file_path)

# 根據不同作業系統自動設定字型，並針對 Linux (GitHub Actions) 強制註冊 Noto CJK 字型
system_name = platform.system()
if system_name == 'Windows':
    plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial']
elif system_name == 'Darwin':  # macOS
    plt.rcParams['font.sans-serif'] = ['PingFang TC', 'Heiti TC', 'Arial']
else:  # Linux / GitHub Actions
    noto_cjk_paths = [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/noto/NotoSansCJK-Regular.ttc'
    ]
    
    font_loaded = False
    for path in noto_cjk_paths:
        if os.path.exists(path):
            try:
                fm.fontManager.addfont(path)
                prop = fm.FontProperties(fname=path)
                font_name = prop.get_name()
                plt.rcParams['font.sans-serif'] = [font_name, 'Noto Sans CJK TC', 'Noto Sans CJK SC', 'DejaVu Sans']
                font_loaded = True
                break
            except Exception:
                pass
                
    if not font_loaded:
        plt.rcParams['font.sans-serif'] = ['Noto Sans CJK TC', 'Noto Sans CJK SC', 'WenQuanYi Micro Hei', 'DejaVu Sans']

# 解決負號無法正常顯示的問題
plt.rcParams['axes.unicode_minus'] = False

MACAU_LAT = 22.1595
MACAU_LON = 113.5685
KM_PER_DEG = 111.32

FORECAST_RADII_MAPPING = {
    0: 15,
    3: 26,
    6: 36,
    12: 58,
    18: 79,
    24: 100,
    36: 135,
    48: 170,
    60: 212.5,
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

def plot_tc_icon(ax, lon, lat, icon_filename, default_color='#DDDFE2', zoom=0.012):
    extent = ax.get_extent(crs=ccrs.PlateCarree())
    if not (extent[0] <= lon <= extent[1] and extent[2] <= lat <= extent[3]):
        return

    icon_path = os.path.join('icon', 'tc_icon', icon_filename)
    if os.path.exists(icon_path):
        try:
            img = mpimg.imread(icon_path)
            imagebox = OffsetImage(img, zoom=0.0042)
            ab = AnnotationBbox(imagebox, (lon, lat), xycoords=ccrs.PlateCarree()._as_mpl_transform(ax), frameon=False)
            ax.add_artist(ab)
            ab.set_zorder(100)
            return
        except Exception:
            pass
    ax.plot(lon, lat, marker='x', color=default_color, markersize=6, transform=ccrs.PlateCarree(), zorder=5)

def add_logo_to_map(ax):
    """將 MSSO(H).png 標誌放置於地圖內部左上角（精緻小尺寸）"""
    logo_path = os.path.join('icon', 'MSSO_icon', 'MSSO(H).png')
    if os.path.exists(logo_path):
        try:
            img = mpimg.imread(logo_path)
            extent = ax.get_extent(crs=ccrs.PlateCarree())
            lon_min, lon_max, lat_min, lat_max = extent
            
            logo_lon = lon_min + (lon_max - lon_min) * 0.08
            logo_lat = lat_max - (lat_max - lat_min) * 0.08
            
            imagebox = OffsetImage(img, zoom=0.02)
            ab = AnnotationBbox(imagebox, (logo_lon, logo_lat), xycoords=ccrs.PlateCarree()._as_mpl_transform(ax), frameon=False)
            ax.add_artist(ab)
            ab.set_zorder(200)
        except Exception:
            pass

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

        if 'current' in cat:
            past_lats.append(lat)
            past_lons.append(lon)
            past_winds.append(wind)

            fcst_hours.append(0)
            fcst_lats.append(lat)
            fcst_lons.append(lon)
            fcst_winds.append(wind)
            fcst_radii.append(FORECAST_RADII_MAPPING.get(0, 15))
        elif 'past' in cat:
            past_lats.append(lat)
            past_lons.append(lon)
            past_winds.append(wind)
        else:
            hr_str = ''.join(filter(str.isdigit, cat))
            hr = int(hr_str) if hr_str else 0
            if hr == 0:
                continue
            fcst_hours.append(hr)
            fcst_lats.append(lat)
            fcst_lons.append(lon)
            fcst_winds.append(wind)
            fcst_radii.append(FORECAST_RADII_MAPPING.get(hr, 100 + hr * 3))

    if fcst_hours:
        sorted_indices = np.argsort(fcst_hours)
        fcst_hours = np.array(fcst_hours)[sorted_indices]
        fcst_lats = np.array(fcst_lats)[sorted_indices]
        fcst_lons = np.array(fcst_lons)[sorted_indices]
        fcst_winds = np.array(fcst_winds)[sorted_indices]
        fcst_radii = np.array(fcst_radii)[sorted_indices]

    return {
        "name": storm_name,
        "past": {"lats": np.array(past_lats), "lons": np.array(past_lons), "wind_kmh": past_winds},
        "forecast": {
            "hours": fcst_hours, 
            "lats": fcst_lats, 
            "lons": fcst_lons, 
            "wind_kmh": fcst_winds,
            "radii_km": fcst_radii
        }
    }

def compute_storm_envelopes(f):
    """計算切分式誤差圓錐（<=72h 與 >72h），確保只在 forecast 含有 >72h 時才建立第二層誤差圓錐"""
    hours = f["hours"]
    lons = f["lons"]
    lats = f["lats"]
    if len(hours) < 2:
        return None, None
    
    radii_deg = np.array(f["radii_km"]) / KM_PER_DEG
    smooth_lons, smooth_lats, interp_hours = create_smooth_track_uniform_time(hours, lons, lats, time_step=1.0)
    smooth_radii = PchipInterpolator(hours, radii_deg)(interp_hours)

    circles_segment1 = [Point(smooth_lons[i], smooth_lats[i]).buffer(smooth_radii[i]) for i in range(len(smooth_lons)) if interp_hours[i] <= 72]
    envelope_first = unary_union(circles_segment1) if circles_segment1 else None

    envelope_second_no_overlap = None
    has_gt_72 = np.any(hours > 72)
    if has_gt_72:
        circles_segment2 = [Point(smooth_lons[i], smooth_lats[i]).buffer(smooth_radii[i]) for i in range(len(smooth_lons)) if interp_hours[i] > 72]
        envelope_second = unary_union(circles_segment2) if circles_segment2 else None

        if len(interp_hours) > 0 and np.any(interp_hours >= 72):
            idx_72h = int(np.argmin(np.abs(interp_hours - 72)))
            circle_72h_geom = Point(smooth_lons[idx_72h], smooth_lats[idx_72h]).buffer(smooth_radii[idx_72h])

            if envelope_second and not envelope_second.is_empty:
                envelope_second = make_valid(envelope_second.difference(circle_72h_geom))
            if envelope_first and not envelope_first.is_empty and envelope_second and not envelope_second.is_empty:
                envelope_second_no_overlap = make_valid(envelope_second.difference(envelope_first))
            else:
                envelope_second_no_overlap = envelope_second

    return envelope_first, envelope_second_no_overlap

def add_macau_range_rings(ax):
    ax.plot(MACAU_LON, MACAU_LAT, marker='o', color='white', markersize=4, transform=ccrs.PlateCarree(), zorder=5)

    outer_km_list = [105, 220, 430, 850]
    outer_label_list = ['100 km', '200 km', '400 km', '800 km']

    for km, label in zip(outer_km_list, outer_label_list):
        deg_radius = km / KM_PER_DEG
        circle = Point(MACAU_LON, MACAU_LAT).buffer(deg_radius)
        ax.add_geometries([circle], crs=ccrs.PlateCarree(), edgecolor="#949494", facecolor='none', linewidth=0.5, alpha=0.5, linestyle='--')

def setup_map_axes(ax, E1, E2, N1, N2):
    """設定地圖範圍、網格及嚴格對齊整數與 5 的倍數之經緯度數值標籤"""
    ax.set_extent([E1, E2, N1, N2], crs=ccrs.PlateCarree())
    
    ax.add_feature(cfeature.NaturalEarthFeature('physical', 'land', '50m', edgecolor="#959a9f", facecolor="#2d363f"), zorder=1)
    ax.add_feature(cfeature.NaturalEarthFeature('physical', 'ocean', '50m', facecolor="#222a35"), zorder=0)
    ax.add_feature(cfeature.BORDERS.with_scale('50m'), linestyle=':', linewidth=0.25, edgecolor="#888888", zorder=3)

    add_macau_range_rings(ax)

    # 1° 網格線對齊整數倍數
    start_1deg_lon = int(math.floor(E1))
    end_1deg_lon = int(math.ceil(E2))
    grid_1deg_lon = np.arange(start_1deg_lon, end_1deg_lon + 1, 1)

    start_1deg_lat = int(math.floor(N1))
    end_1deg_lat = int(math.ceil(N2))
    grid_1deg_lat = np.arange(start_1deg_lat, end_1deg_lat + 1, 1)

    # 5° 網格線與標籤對齊 5 的倍數
    start_5deg_lon = int(math.floor(E1 / 5.0) * 5)
    end_5deg_lon = int(math.ceil(E2 / 5.0) * 5)
    major_5deg_lon = np.arange(start_5deg_lon, end_5deg_lon + 1, 5)

    start_5deg_lat = int(math.floor(N1 / 5.0) * 5)
    end_5deg_lat = int(math.ceil(N2 / 5.0) * 5)
    major_5deg_lat = np.arange(start_5deg_lat, end_5deg_lat + 1, 5)

    ax.gridlines(xlocs=grid_1deg_lon, ylocs=grid_1deg_lat, crs=ccrs.PlateCarree(), draw_labels=False, linewidth=0.15, color='gray', alpha=0.3, linestyle='--', zorder=-7)
    ax.gridlines(xlocs=major_5deg_lon, ylocs=major_5deg_lat, crs=ccrs.PlateCarree(), draw_labels=False, linewidth=0.6, color='gray', alpha=0.4, linestyle='--', zorder=-6)

    gl_label = ax.gridlines(
        xlocs=major_5deg_lon, ylocs=major_5deg_lat,
        crs=ccrs.PlateCarree(),
        draw_labels={"bottom": "x",  "left": "y"}, 
        linewidth=0,
        xlabel_style={"size": 6, "color": "white", "alpha": 0.8},
        ylabel_style={"size": 6, "color": "white", "alpha": 0.8}
    )
    gl_label.xpadding = -6
    gl_label.ypadding = -6

def find_best_label_position(flon, flat, obstacles, map_extent, candidate_offsets):
    """尋找既不與軌跡/圓錐重疊、又不超出地圖範圍的最佳標籤偏移量"""
    E1, E2, N1, N2 = map_extent
    # 安全邊界：確保標籤框不會貼齊或超出地圖邊緣
    safe_box = box(E1 + 2.5, N1 + 2.0, E2 - 2.5, N2 - 2.0)
    
    best_dx, best_dy = candidate_offsets[0]
    
    # 優先尋找完全不碰撞軌跡且完全在安全邊界內的候選位置
    for dx, dy in candidate_offsets:
        label_box = Point(flon + dx, flat + dy).buffer(1.8)
        if not label_box.intersects(obstacles) and safe_box.contains(label_box):
            return dx, dy
            
    # 若無完美位置，退而求其次尋找距離障礙物最遠，且儘量留在安全範圍內的位置
    best_score = -999999.0
    for dx, dy in candidate_offsets:
        label_box = Point(flon + dx, flat + dy).buffer(1.8)
        dist_to_obs = label_box.distance(obstacles)
        
        # 評分標準：距離障礙物越遠越好，若在安全範圍內給予額外加分
        score = dist_to_obs
        if safe_box.contains(label_box):
            score += 50.0
        
        if score > best_score:
            best_score = score
            best_dx, best_dy = dx, dy
            
    return best_dx, best_dy

def generate_maps():
    files = ['A', 'B', 'C', 'D', 'E', 'F']
    valid_storms = {}

    for prefix in files:
        path = f'TCdata/{prefix}.csv'
        if os.path.exists(path):
            try:
                valid_storms[prefix] = parse_tc_csv(path)
            except Exception:
                pass

    if not valid_storms:
        return

    candidate_offsets = [
        (1.8, 0.0),    # 右側
        (-6.5, 0.0),   # 左側
        (0.0, 3.0),    # 上方
        (0.0, -3.0),   # 下方
        (1.8, 3.0),    # 右上方
        (-6.5, 3.0),   # 左上方
        (1.8, -3.0),   # 右下方
        (-6.5, -3.0),  # 左下方
        (3.5, 1.5),    # 遠右方
        (-6.0, 1.5)    # 遠左方
    ]

    # 1. 產生綜合路徑圖 (all.png)
    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
    
    all_map_extent = [100, 160, 5, 50]
    setup_map_axes(ax, *all_map_extent)

    all_storm_geoms = []
    for prefix, data in valid_storms.items():
        obs_parts = []
        p = data["past"]
        f = data["forecast"]
        if len(p["lats"]) > 1:
            obs_parts.append(LineString(zip(p["lons"], p["lats"])))
        for plon, plat in zip(p["lons"], p["lats"]):
            obs_parts.append(Point(plon, plat).buffer(0.8))
        if len(f["hours"]) > 1:
            obs_parts.append(LineString(zip(f["lons"], f["lats"])))
            for flon, flat in zip(f["lons"], f["lats"]):
                obs_parts.append(Point(flon, flat).buffer(1.5))
            env_first, env_sec = compute_storm_envelopes(f)
            if env_first and not env_first.is_empty:
                obs_parts.append(env_first)
            if env_sec and not env_sec.is_empty:
                obs_parts.append(env_sec)
        if obs_parts:
            all_storm_geoms.append(unary_union(obs_parts))
    combined_obstacles = unary_union(all_storm_geoms) if all_storm_geoms else Point(0, 0)
    placed_labels_geom = []

    for prefix, data in valid_storms.items():
        p = data["past"]
        f = data["forecast"]
        sname = data["name"] if data["name"] else f"TC {prefix}"

        if len(p["lats"]) > 0:
            ax.plot(p["lons"], p["lats"], color='white', linewidth=1.5, transform=ccrs.PlateCarree(), alpha=0.7)
            for plon, plat, w in zip(p["lons"], p["lats"], p["wind_kmh"]):
                dot_color, _, _ = get_tc_style(w)
                ax.plot(plon, plat, marker='o', color=dot_color, markersize=4, transform=ccrs.PlateCarree(), zorder=4)

        if len(f["hours"]) > 1:
            smooth_lons, smooth_lats, _ = create_smooth_track_uniform_time(f["hours"], f["lons"], f["lats"], time_step=1.0)
            env_first, env_sec = compute_storm_envelopes(f)

            if env_first and not env_first.is_empty:
                ax.add_geometries([env_first], crs=ccrs.PlateCarree(), facecolor='white', alpha=0.20)
            if env_sec and not env_sec.is_empty:
                ax.add_geometries([env_sec], crs=ccrs.PlateCarree(), facecolor='white', alpha=0.10)

            ax.plot(smooth_lons, smooth_lats, color='white', linestyle='--', linewidth=1.5, transform=ccrs.PlateCarree(), label=sname, zorder=4)

            for flon, flat, w in zip(f["lons"], f["lats"], f["wind_kmh"]):
                _, icon_file, _ = get_tc_style(w)
                plot_tc_icon(ax, flon, flat, icon_file, zoom=0.10)

            if len(f["lons"]) > 0:
                flon, flat = f["lons"][0], f["lats"][0]
                current_obstacle = unary_union([combined_obstacles] + placed_labels_geom) if placed_labels_geom else combined_obstacles
                
                best_dx, best_dy = find_best_label_position(flon, flat, current_obstacle, all_map_extent, candidate_offsets)

                final_label_box = Point(flon + best_dx, flat + best_dy).buffer(1.8)
                placed_labels_geom.append(final_label_box)

                ax.text(flon + best_dx, flat + best_dy, sname, 
                        transform=ccrs.PlateCarree(), color='white', fontsize=9, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='black', alpha=0.6, edgecolor='none'),
                        zorder=102)

    add_logo_to_map(ax)
    plt.savefig('output/TC/all.png', dpi=800, bbox_inches='tight')
    plt.close()

    # 2. 逐一產生單一氣旋路徑圖與誤差圓錐 (A.png ~ F.png)
    for prefix, data in valid_storms.items():
        fig = plt.figure(figsize=(12, 9))
        ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())

        p = data["past"]
        f = data["forecast"]
        sname = data["name"] if data["name"] else f"熱帶氣旋 {prefix}"
        has_forecast = len(f["hours"]) > 1

        envelope_first = envelope_second_no_overlap = None
        if has_forecast:
            envelope_first, envelope_second_no_overlap = compute_storm_envelopes(f)
            smooth_lons, smooth_lats, _ = create_smooth_track_uniform_time(f["hours"], f["lons"], f["lats"], time_step=1.0)

        if has_forecast and len(f["lats"]) > 0:
            target_lats = f["lats"]
            target_lons = f["lons"]
        else:
            target_lats = p["lats"]
            target_lons = p["lons"]

        if len(target_lats) > 0:
            lat_min_margin = 3.5
            lat_max_margin = 3.5
            lon_min_margin = 4.0
            lon_max_margin = 4.0

            lat_min = target_lats.min() - lat_min_margin
            lat_max = target_lats.max() + lat_max_margin
            
            lon_max_raw = target_lons.max() + lon_max_margin
            lon_max = min(170.0, lon_max_raw)
            
            lat_span = lat_max - lat_min
            target_lon_span = lat_span * 1.5
            lon_min = lon_max - target_lon_span
            
            single_map_extent = [lon_min, lon_max, lat_min, lat_max]
            setup_map_axes(ax, *single_map_extent)
        else:
            single_map_extent = [120, 170, 5, 38.33]
            setup_map_axes(ax, *single_map_extent)

        if has_forecast:
            if envelope_first and not envelope_first.is_empty:
                ax.add_geometries([envelope_first], crs=ccrs.PlateCarree(), facecolor='white', alpha=0.20)
            if envelope_second_no_overlap and not envelope_second_no_overlap.is_empty:
                ax.add_geometries([envelope_second_no_overlap], crs=ccrs.PlateCarree(), facecolor='white', alpha=0.10)

        if len(p["lats"]) > 0:
            ax.plot(p["lons"], p["lats"], color='white', linewidth=1.5, transform=ccrs.PlateCarree())
            for plon, plat, w in zip(p["lons"], p["lats"], p["wind_kmh"]):
                dot_color, _, _ = get_tc_style(w)
                ax.plot(plon, plat, marker='o', color=dot_color, markersize=5, transform=ccrs.PlateCarree(), zorder=4)

        if has_forecast and len(f["lats"]) > 1:
            ax.plot(smooth_lons, smooth_lats, color='white', linestyle='--', linewidth=1.5, label=sname, transform=ccrs.PlateCarree(), zorder=4)
            for flon, flat, w in zip(f["lons"], f["lats"], f["wind_kmh"]):
                _, icon_file, _ = get_tc_style(w)
                plot_tc_icon(ax, flon, flat, icon_file, zoom=0.14)

            if len(f["lons"]) > 0:
                flon, flat = f["lons"][0], f["lats"][0]
                
                # 建立單一圖檔的氣旋障礙物 (軌跡、點位、誤差圓錐)
                obs_parts = []
                if len(p["lats"]) > 1:
                    obs_parts.append(LineString(zip(p["lons"], p["lats"])))
                for plon, plat in zip(p["lons"], p["lats"]):
                    obs_parts.append(Point(plon, plat).buffer(0.8))
                if len(f["hours"]) > 1:
                    obs_parts.append(LineString(zip(f["lons"], f["lats"])))
                    for fx, fy in zip(f["lons"], f["lats"]):
                        obs_parts.append(Point(fx, fy).buffer(1.5))
                    if envelope_first and not envelope_first.is_empty:
                        obs_parts.append(envelope_first)
                    if envelope_second_no_overlap and not envelope_second_no_overlap.is_empty:
                        obs_parts.append(envelope_second_no_overlap)
                storm_obstacles = unary_union(obs_parts) if obs_parts else Point(0, 0)

                best_dx, best_dy = find_best_label_position(flon, flat, storm_obstacles, single_map_extent, candidate_offsets)

                ax.text(flon + best_dx, flat + best_dy, sname, 
                        transform=ccrs.PlateCarree(), color='white', fontsize=11, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7, edgecolor='none'),
                        zorder=102)

        add_logo_to_map(ax)
        plt.savefig(f'output/TC/{prefix}.png', dpi=800, bbox_inches='tight')
        plt.close()

if __name__ == '__main__':
    generate_maps()
