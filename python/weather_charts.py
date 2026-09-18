import os
import requests
import numpy as np
import matplotlib.pyplot as plt

def generate_weather_charts():
    os.makedirs("weather_chart", exist_ok=True)
    
    # Specified coordinates bounds: Lon [105, 145], Lat [10, 40]
    lons = np.linspace(105, 145, 5)
    lats = np.linspace(10, 40, 5)
    
    layers = ['surface', '925hPa', '850hPa', '700hPa', '500hPa', '200hPa']
    hours = [0, 12, 24, 36, 48]
    
    print("Fetching weather grid data from Open-Meteo...")
    grid_data = {}
    for lat in lats:
        for lon in lons:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "hourly": [
                    "temperature_2m", 
                    "temperature_925hPa", "temperature_850hPa", 
                    "temperature_700hPa", "temperature_500hPa", "temperature_200hPa"
                ],
                "forecast_days": 3
            }
            try:
                res = requests.get(url, params=params, timeout=10)
                if res.status_code == 200:
                    grid_data[(lat, lon)] = res.json().get('hourly', {})
            except Exception as e:
                print(f"Error fetching lat {lat}, lon {lon}: {e}")

    LON, LAT = np.meshgrid(lons, lats)
    
    print("Rendering static chart images...")
    for hour in hours:
        for layer in layers:
            fig, ax = plt.subplots(figsize=(9, 6))
            
            values = np.zeros(LON.shape)
            for i, lat in enumerate(lats):
                for j, lon in enumerate(lons):
                    h_data = grid_data.get((lat, lon), {})
                    key = 'temperature_2m' if layer == 'surface' else f'temperature_{layer}'
                    val_list = h_data.get(key, [])
                    values[i, j] = val_list[hour] if len(val_list) > hour else 25.0

            # Contour plot generation
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
            
            # Dark theme styling for chart background
            fig.patch.set_facecolor('#0b1324')
            ax.set_facecolor('#151f32')
            
            filename = f"output/weather_chart/chart_{layer}_{hour}h.png"
            plt.savefig(filename, bbox_inches='tight', dpi=150, facecolor=fig.get_facecolor())
            plt.close(fig)
            
    print("All weather chart images successfully generated inside 'weather_chart/'.")

if __name__ == "__main__":
    generate_weather_charts()
