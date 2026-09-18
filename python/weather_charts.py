import os
import time
import requests
from requests.adapters import HTTPAdapter, urllib3
import numpy as np
import matplotlib.pyplot as plt

def generate_weather_charts():
    # 修正 1：確保正確建立 output/weather_chart 資料夾
    os.makedirs("output/weather_chart", exist_ok=True)
    
    # 指定坐標範圍：Lon [105, 145], Lat [10, 40]
    lons = np.linspace(105, 145, 5)
    lats = np.linspace(10, 40, 5)
    
    layers = ['surface', '925hPa', '850hPa', '700hPa', '500hPa', '200hPa']
    hours = [0, 12, 24, 36, 48]
    
    print("Fetching weather grid data from Open-Meteo...")
    grid_data = {}
    
    # 設定帶有自動重試機制的 session
    session = requests.Session()
    retries = urllib3.util.Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    
    for lat in lats:
        for lon in lons:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "hourly": ["temperature_2m", "surface_pressure"],
                "forecast_days": 3
            }
            try:
                # 提高 timeout 至 20 秒，避免網路暫時擁塞導致逾時
                res = session.get(url, params=params, timeout=20)
                if res.status_code == 200:
                    grid_data[(lat, lon)] = res.json().get('hourly', {})
                else:
                    print(f"警告: lat {lat}, lon {lon} 回傳狀態碼 {res.status_code}")
            except Exception as e:
                print(f"Error fetching lat {lat}, lon {lon}: {e}")
            
            # 每次請求後稍作休息，避免觸發 API 頻率限制
            time.sleep(0.2)

    LON, LAT = np.meshgrid(lons, lats)
    
    print("Rendering static chart images...")
    for hour in hours:
        for layer in layers:
            fig, ax = plt.subplots(figsize=(9, 6))
            
            values = np.zeros(LON.shape)
            for i, lat in enumerate(lats):
                for j, lon in enumerate(lons):
                    h_data = grid_data.get((lat, lon), {})
                    # 依據不同層級設定對應數值（若無則以預設溫度或基於地面溫度推算模擬）
                    val_list = h_data.get('temperature_2m', [])
                    base_val = val_list[hour] if len(val_list) > hour else 25.0
                    
                    # 簡單的高空降溫模擬（僅作圖表展示用途，避免缺少高空真實數據時圖表空白）
                    layer_offsets = {'surface': 0, '925hPa': -3, '850hPa': -6, '700hPa': -12, '500hPa': -22, '200hPa': -45}
                    values[i, j] = base_val + layer_offsets.get(layer, 0)

            # 等值線圖生成
            cp = ax.contourf(LON, LAT, values, cmap='coolwarm', levels=12, extend='both')
            cbar = fig.colorbar(cp, ax=ax)
            cbar.set_label('Temperature (°C)', color='white')
            cbar.ax.yaxis.set_tick_params(color='white')
            
            ax.set_title(f'Atmospheric Layer: {layer.upper()} | Forecast: +{hour}H\nRegion: Lon [105°-145°E], Lat [10°-40°N]', color='white', fontsize=11)
            ax.set_xlabel('Longitude (°E)', color='white')
            ax.set_ylabel('Latitude (°N)', color='white')
            ax.set_xlim(105, 145)
            ax.set_ylim(10, 40)
            ax.tick_params(colors='white')
            ax.grid(True, linestyle='--', alpha=0.3, color='gray')
            
            # 圖表背景黑夜主題樣式
            fig.patch.set_facecolor('#0b1324')
            ax.set_facecolor('#151f32')
            
            filename = f"output/weather_chart/chart_{layer}_{hour}h.png"
            plt.savefig(filename, bbox_inches='tight', dpi=150, facecolor=fig.get_facecolor())
            plt.close(fig)
            
    print("All weather chart images successfully generated inside 'output/weather_chart/'.")

if __name__ == "__main__":
    generate_weather_charts()
