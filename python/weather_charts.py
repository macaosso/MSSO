import os
import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import numpy as np
import requests
from scipy.interpolate import griddata
from scipy.ndimage import maximum_filter, minimum_filter

def generate_weather_charts():
    # 1. 確保輸出目錄存在
    os.makedirs("output/weather_chart", exist_ok=True)
    
    # 2. 設定分析區域網格 (Lon: 105°~145°E, Lat: 10°~40°N)
    lons = np.linspace(105, 145, 9)
    lats = np.linspace(10, 40, 7)
    lon_mesh, lat_mesh = np.meshgrid(lons, lats)
    flat_lons = lon_mesh.flatten()
    flat_lats = lat_mesh.flatten()
    
    layers = ['surface', '925hPa', '850hPa', '700hPa', '500hPa', '200hPa']
    hours = [0, 12, 24, 36, 48]
    
    print("Fetching multi-layer weather grid data from Open-Meteo...")
    
    # 批次組裝坐標參數
    lat_str = ','.join(map(str, flat_lats))
    lon_str = ','.join(map(str, flat_lons))
    
    # 同時請求海平面氣壓與各高空層位勢高度 (Geopotential Height)
    hourly_vars = [
        'pressure_msl',
        'geopotential_height_925hPa',
        'geopotential_height_850hPa',
        'geopotential_height_700hPa',
        'geopotential_height_500hPa',
        'geopotential_height_200hPa'
    ]
    vars_str = ','.join(hourly_vars)
    
    url_grid = f'https://api.open-meteo.com/v1/forecast?latitude={lat_str}&longitude={lon_str}&hourly={vars_str}&forecast_days=3'

    try:
        res = requests.get(url_grid, timeout=30)
        res_grid = res.json()
        if isinstance(res_grid, dict):
            if res_grid.get('error'):
                raise RuntimeError(f"Open-Meteo API Error: {res_grid.get('reason')}")
            res_grid = [res_grid]
    except Exception as e:
        print(f"API 批次請求發生錯誤: {e}")
        res_grid = [{} for _ in range(len(flat_lats))]

    # 建立網格資料字典
    grid_data_dict = {}
    for idx, (lat, lon) in enumerate(zip(flat_lats, flat_lons)):
        loc_hourly = res_grid[idx].get('hourly', {}) if idx < len(res_grid) else {}
        grid_data_dict[(lat, lon)] = loc_hourly

    # 3. 建立平滑插值網格
    interp_lon, interp_lat = np.meshgrid(
        np.linspace(105, 145, 200), np.linspace(10, 40, 150)
    )

    def find_extrema_coords(grid_z, grid_x, grid_y, mode='max', n=2):
        if mode == 'max':
            local_mask = grid_z == maximum_filter(grid_z, size=15, mode='constant', cval=-9999)
        else:
            local_mask = grid_z == minimum_filter(grid_z, size=15, mode='constant', cval=9999)

        y_indices, x_indices = np.where(local_mask)
        values = grid_z[y_indices, x_indices]
        sorted_idx = np.argsort(values)[::-1] if mode == 'max' else np.argsort(values)

        points = []
        for idx in sorted_idx:
            yi, xi = y_indices[idx], x_indices[idx]
            points.append((grid_x[yi, xi], grid_y[yi, xi], grid_z[yi, xi]))
            if len(points) >= n:
                break
        return points

    print("Rendering multi-layer and multi-hour weather charts...")

    # 4. 迴圈遍歷所有時效與大氣層
    for hour in hours:
        for layer in layers:
            # 依據層級對應 Open-Meteo 變數與等值線間距
            if layer == 'surface':
                var_key = 'pressure_msl'
                contour_interval = 2
                default_val = 1013.0
            else:
                var_key = f'geopotential_height_{layer}'
                contour_interval = 4 if layer in ['500hPa', '200hPa'] else 2
                # 不同高空層的典型位勢高度基準 (gpm)
                defaults = {'925hPa': 750, '850hPa': 1450, '700hPa': 3100, '500hPa': 5850, '200hPa': 11800}
                default_val = defaults.get(layer, 1500.0)

            raw_values = []
            for lat in lats:
                for lon in lons:
                    h_dict = grid_data_dict.get((lat, lon), {})
                    val_list = h_dict.get(var_key, [])
                    val = val_list[hour] if len(val_list) > hour else default_val
                    raw_values.append(val if val is not None else default_val)

            raw_values = np.array(raw_values)

            # 空間三次方插值 (Cubic Interpolation)
            grid_2d = griddata(
                (flat_lons, flat_lats),
                raw_values,
                (interp_lon, interp_lat),
                method='cubic',
                fill_value=np.nan
            )
            grid_2d = np.nan_to_num(grid_2d, nan=np.nanmean(raw_values))

            # 計算高壓 (H) 與低壓 (L) 中心
            highs = find_extrema_coords(grid_2d, interp_lon, interp_lat, mode='max', n=2)
            lows = find_extrema_coords(grid_2d, interp_lon, interp_lat, mode='min', n=2)

            # 5. 使用 Cartopy 繪製高質感天氣圖
            fig, ax = plt.subplots(
                figsize=(11, 8), subplot_kw={'projection': ccrs.PlateCarree()}
            )
            ax.set_extent([105, 145, 10, 40], crs=ccrs.PlateCarree())

            ax.add_feature(cfeature.LAND, facecolor='#f4f8f3')
            ax.add_feature(cfeature.OCEAN, facecolor='#e0f0ff')
            ax.add_feature(cfeature.COASTLINE, linewidth=0.6)
            ax.add_feature(cfeature.BORDERS, linestyle=':', alpha=0.5)
            ax.gridlines(draw_labels=True, linestyle='--', alpha=0.3)

            # 計算等值線級距
            min_v = np.floor(np.nanmin(grid_2d) / contour_interval) * contour_interval
            max_v = np.ceil(np.nanmax(grid_2d) / contour_interval) * contour_interval
            contour_levels = np.arange(min_v, max_v + contour_interval, contour_interval)

            cs = ax.contour(
                interp_lon,
                interp_lat,
                grid_2d,
                levels=contour_levels,
                colors='black',
                linewidths=0.7,
            )
            ax.clabel(cs, inline=True, fontsize=8, fmt='%d')

            # 標註高壓 (H) 與低壓 (L)
            for h in highs:
                ax.text(h[0], h[1], 'H', color='red', fontsize=13, weight='bold', ha='center', va='center', transform=ccrs.PlateCarree())
                ax.text(h[0], h[1] - 0.7, f'{h[2]:.0f}', color='red', fontsize=7, weight='bold', ha='center', transform=ccrs.PlateCarree())

            for l in lows:
                ax.text(l[0], l[1], 'L', color='blue', fontsize=13, weight='bold', ha='center', va='center', transform=ccrs.PlateCarree())
                ax.text(l[0], l[1] - 0.7, f'{l[2]:.0f}', color='blue', fontsize=7, weight='bold', ha='center', transform=ccrs.PlateCarree())

            # 標題與時效標記
            current_time = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:00 UTC')
            layer_title = layer.upper() if layer != 'surface' else 'Mean Sea Level (Surface)'
            plt.title(f'Synoptic Chart: {layer_title} | Forecast: +{hour}H', fontsize=11, weight='bold', loc='left')
            plt.title(f'VALID: {current_time}', fontsize=9, loc='right')

            # 儲存至對應命名檔案
            filename = f"output/weather_chart/chart_{layer}_{hour}h.png"
            plt.savefig(filename, format='png', bbox_inches='tight', dpi=120)
            plt.close(fig)
            print(f"Successfully generated: {filename}")

    print("All multi-layer and multi-hour weather charts successfully generated inside 'output/weather_chart/'.")

if __name__ == "__main__":
    generate_weather_charts()
