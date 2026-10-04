import os
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.interpolate as si
from scipy.ndimage import maximum_filter

import cartopy.crs as ccrs
import cartopy.feature as cfeature


# 稀疏筛选点位函数，防止文字重叠
def sample_valid_points(
    df_sample, lon_col, lat_col, rain_col, min_dist_deg=0.03, min_rain=1.0
):
    df_filter = df_sample[df_sample[rain_col] >= min_rain].copy()
    if df_filter.empty:
        return pd.DataFrame()

    selected = []
    lons = df_filter[lon_col].values
    lats = df_filter[lat_col].values
    rains = df_filter[rain_col].values

    for lon, lat, rain in zip(lons, lats, rains):
        too_close = False
        for slon, slat, _ in selected:
            dist = np.sqrt((lon - slon) ** 2 + (lat - slat) ** 2)
            if dist < min_dist_deg:
                too_close = True
                break
        if not too_close:
            selected.append([lon, lat, rain])
    return pd.DataFrame(selected, columns=[lon_col, lat_col, rain_col])


# 雨量文字颜色映射
def get_text_color(val):
    if val < 1:
        return "#15438e"
    elif val < 5:
        return "#2fdbeb"
    elif val < 10:
        return "#0F9C5D"
    elif val < 20:
        return "#52ee27"
    elif val < 50:
        return "#ffdd00"
    elif val < 80:
        return "#ff0000"
    elif val < 100:
        return "#4a4747"
    else:
        return "#6C074E"


# 封装单张图绘图逻辑
def plot_rain_map(ax, df_frame, lon_col, lat_col, rain_col, valid_dt_obj):
    # 插值平滑雨量场
    xi = np.linspace(df_frame[lon_col].min(), df_frame[lon_col].max(), 400)
    yi = np.linspace(df_frame[lat_col].min(), df_frame[lat_col].max(), 400)
    Xi, Yi = np.meshgrid(xi, yi)

    Zi = si.griddata(
        (df_frame[lon_col], df_frame[lat_col]),
        df_frame[rain_col],
        (Xi, Yi),
        method="cubic",
    )
    Zi[Zi < 0.1] = np.nan

    # 局部峰值检测
    window_size = 8
    peak_min_threshold = 10.0
    max_filtered = maximum_filter(Zi, size=window_size)
    peak_mask = (Zi == max_filtered) & (~np.isnan(Zi))

    peak_lon_arr = Xi[peak_mask]
    peak_lat_arr = Yi[peak_mask]
    peak_val_arr = Zi[peak_mask]

    valid_peak_idx = peak_val_arr >= peak_min_threshold
    peak_lon_arr = peak_lon_arr[valid_peak_idx]
    peak_lat_arr = peak_lat_arr[valid_peak_idx]
    peak_val_arr = peak_val_arr[valid_peak_idx]

    # 地图范围
    lon_min, lon_max = 113, 114.4
    lat_min, lat_max = 21.5, 22.75
    ax.set_extent([lon_min, lon_max, lat_min, lat_max], crs=ccrs.PlateCarree())

    # 底图要素
    ax.add_feature(
        cfeature.BORDERS, linestyle=":", linewidth=1, edgecolor="dimgray"
    )
    ax.add_feature(cfeature.LAND, edgecolor="#959a9f", facecolor="#2d363f")
    ax.add_feature(cfeature.OCEAN, facecolor="#222a35")

    # 网格线
    grid_1deg_lon = np.arange(lon_min, lon_max + 1, 0.02)
    grid_1deg_lat = np.arange(lat_min, lat_max + 1, 0.02)
    major_5deg_lon = np.arange(lon_min, lon_max + 1, 0.1)
    major_5deg_lat = np.arange(lat_min, lat_max + 1, 0.1)

    ax.gridlines(
        xlocs=grid_1deg_lon,
        ylocs=grid_1deg_lat,
        draw_labels=False,
        linewidth=0.15,
        color="gray",
        alpha=0.25,
        linestyle="--",
        zorder=-9,
    )
    ax.gridlines(
        xlocs=major_5deg_lon,
        ylocs=major_5deg_lat,
        draw_labels=False,
        linewidth=0.6,
        color="gray",
        alpha=0.4,
        linestyle="--",
        zorder=-8,
    )

    gl_label = ax.gridlines(
        xlocs=major_5deg_lon,
        ylocs=major_5deg_lat,
        draw_labels={"bottom": "x", "left": "y"},
        linewidth=0,
        xlabel_style={"size": 6, "color": "white", "alpha": 0.8},
        ylabel_style={"size": 6, "color": "white", "alpha": 0.8},
    )
    gl_label.xpadding = -6
    gl_label.ypadding = -6

    # 澳门雷达圈
    MACAU_LAT = 22.1595
    MACAU_LON = 113.5685
    KM_PER_DEG = 111.32
    labels = ["10 km", "25 km", "50 km", "100 km"]
    for km, label in zip([10, 25, 50, 100], labels):
        radius_deg = km / KM_PER_DEG
        circle = plt.Circle(
            (MACAU_LON, MACAU_LAT),
            radius_deg,
            color="#949494",
            fill=False,
            linewidth=0.5,
            alpha=0.5,
            linestyle="--",
            transform=ccrs.PlateCarree(),
        )
        ax.add_patch(circle)
        ax.text(
            MACAU_LON,
            MACAU_LAT - radius_deg - 0.025,
            label,
            color="white",
            alpha=0.5,
            fontsize=6,
            ha="center",
            va="top",
            transform=ccrs.PlateCarree(),
        )
    ax.plot(MACAU_LON, MACAU_LAT, "o", color="white", markersize=5)

    # 填色雨量场
    levels = [0.1, 1, 5, 10, 20, 50, 80, 100]
    colors = [
        "#15438e",
        "#2fdbeb",
        "#0F9C5D",
        "#52ee27",
        "#ffdd00",
        "#ff0000",
        "#4a4747",
        "#6C074E",
    ]
    cf = ax.contourf(
        Xi,
        Yi,
        Zi,
        levels=levels,
        colors=colors,
        extend="max",
        alpha=0.6,
        transform=ccrs.PlateCarree(),
    )

    # 稀疏站点雨量标注
    label_df = sample_valid_points(
        df_frame, lon_col, lat_col, rain_col, min_dist_deg=0.02, min_rain=2.0
    )
    if not label_df.empty:
        for _, row in label_df.iterrows():
            lon = row[lon_col]
            lat = row[lat_col]
            if not (lon_min <= lon <= lon_max and lat_min <= lat <= lat_max):
                continue
            rain_val = round(row[rain_col])
            txt_color = get_text_color(rain_val)
            ax.text(
                lon + 0.003,
                lat + 0.003,
                f"{rain_val}",
                fontsize=6,
                color=txt_color,
                weight="bold",
                alpha=0.95,
                transform=ccrs.PlateCarree(),
            )

    # 峰值红点+标注
    ax.scatter(
        peak_lon_arr,
        peak_lat_arr,
        c="#ff2222",
        s=14,
        zorder=12,
        transform=ccrs.PlateCarree(),
    )
    for plon, plat, pval in zip(peak_lon_arr, peak_lat_arr, peak_val_arr):
        if not (lon_min <= plon <= lon_max and lat_min <= plat <= lat_max):
            continue
        p_round = round(pval)
        peak_txt_clr = get_text_color(p_round)
        ax.text(
            plon + 0.005,
            plat + 0.005,
            f"{p_round}",
            fontsize=7,
            weight="bold",
            color=peak_txt_clr,
            alpha=1.0,
            zorder=13,
            transform=ccrs.PlateCarree(),
        )

    # Top-left MST time text box
    date_time = valid_dt_obj.strftime("%Y-%m-%d  %H:%M") + " MST"
    ax.text(
        0.05,
        0.95,
        date_time,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=10,
        color="white",
        alpha=0.9,
        bbox=dict(facecolor="black", alpha=0.3, pad=3, edgecolor="none"),
        zorder=10,
    )

    # White axis ticks
    ax.tick_params(axis="x", colors="white")
    ax.tick_params(axis="y", colors="white")
    return cf


# =============================
# MAIN EXECUTION
# =============================
if __name__ == "__main__":
    output_dir = os.path.join("output", "radar")
    os.makedirs(output_dir, exist_ok=True)

    csv_file = "https://data.weather.gov.hk/weatherAPI/hko_data/F3/Gridded_rainfall_nowcast_tc.csv"
    df = pd.read_csv(csv_file, encoding="utf-8-sig")
    df.columns = [col.strip() for col in df.columns]

    # Auto detect columns
    lat_col = next(col for col in df.columns if "緯度" in col)
    lon_col = next(col for col in df.columns if "經度" in col)
    rain_col = next(col for col in df.columns if "雨量" in col)
    time_col = next(
        (c for c in df.columns if "時間" in c and ("完結" in c or "結束" in c)),
        None,
    )

    # Clean numeric data
    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")
    df[rain_col] = pd.to_numeric(df[rain_col], errors="coerce")
    df = df.dropna()

    df[time_col] = df[time_col].astype(str)
    unique_times = sorted(df[time_col].unique())

    # Generate an image for each timestamp (typically 4 frames)
    for idx, time_str in enumerate(unique_times, start=1):
        df_frame = df[df[time_col] == time_str].copy()
        df_frame = df_frame[df_frame[rain_col] > 0]

        if df_frame.empty:
            continue

        valid_dt = datetime.strptime(time_str, "%Y%m%d%H%M")

        fig, ax = plt.subplots(
            figsize=(10, 10), subplot_kw={"projection": ccrs.PlateCarree()}
        )
        plot_rain_map(ax, df_frame, lon_col, lat_col, rain_col, valid_dt)

        save_path = os.path.join(output_dir, f"Rain{idx}.png")
        plt.savefig(
            save_path,
            dpi=400,
            bbox_inches="tight",
            facecolor="#222a35",
            edgecolor="none",
        )
        plt.close(fig)
        print(f"Successfully generated: {save_path}")
