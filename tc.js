const tcText = ` `;

const tcWarnings = ``;

const TC_WARNING_DATA = {
  mainTitle: "受熱帶氣旋「沙德爾」可能發佈之警報",
  updateTimeText: "2026-09-02  14:20 MST 更新",
  tableRows: [
    { signal: "注意警報", period: "", probability: "" },
    { signal: "戒備警報", period: "", probability: "" },
    { signal: "強風警報", period: "", probability: "" },
    { signal: "烈風警報", period: "", probability: "" },
    { signal: "暴風警報", period: "", probability: "" },
    { signal: "颶風警報", period: "", probability: "" },
    { signal: "風暴潮觀察警報", period: "", probability: "" },
    { signal: "風暴潮戒備警報", period: "", probability: "" },
    { signal: "風暴潮危險警報", period: "", probability: "" },   
  ]
};

// 自動將純文字的空行轉為段落與適當間距的輔助函數
function formatTextToHtml(text) {
  if (!text) return '';
  return text
    .trim()
    .split(/\n\s*\n/)
    .map(paragraph => `<p class="mb-3 last:mb-0">${paragraph.trim().replace(/\n/g, '<br>')}</p>`)
    .join('');
}

function renderTcForecastTable(data) {
  const tableCard = document.getElementById('tcForecastTableCard');
  const tableContent = document.getElementById('tcTableContent');
  const mainTitleEl = document.getElementById('tableMainTitle');
  const updateTimeEl = document.getElementById('tableUpdateTime');

  if (!tableCard || !tableContent || !data || !Array.isArray(data.tableRows)) {
    if (tableCard) tableCard.style.display = 'none';
    return;
  }

  // 規則 2：只過濾出 probability 不為空的行
  const validRows = data.tableRows.filter(row => row.probability && row.probability.trim() !== '');

  // 規則 2：若全部行的 probability 都為空，隱藏整個表格區塊
  if (validRows.length === 0) {
    tableCard.style.display = 'none';
    return;
  }

  if (mainTitleEl) mainTitleEl.textContent = data.mainTitle || '';
  if (updateTimeEl) updateTimeEl.textContent = data.updateTimeText || '';

  let html = `
    <table class="w-full text-left border-collapse">
      <thead>
        <tr class="border-b border-slate-200 dark:border-slate-800 text-xs font-semibold text-slate-500 dark:text-slate-400">
          <th class="py-2.5 px-3">警報</th>
          <th class="py-2.5 px-3">發佈時段</th>
          <th class="py-2.5 px-3">機率</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-slate-100 dark:divide-slate-800 text-sm">
  `;

  validRows.forEach(row => {
    html += `
      <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
        <td class="py-3 px-3 font-medium text-slate-800 dark:text-slate-200">${row.signal || ''}</td>
        <td class="py-3 px-3 text-slate-600 dark:text-slate-300">${row.period || '-'}</td>
        <td class="py-3 px-3 text-slate-600 dark:text-slate-300">${row.probability || '-'}</td>
      </tr>
    `;
  });

  html += `
      </tbody>
    </table>
  `;

  tableContent.innerHTML = html;
  tableCard.style.display = 'block';
}

// 風速分級規則對應表
const TC_INTENSITY_TABLE = [
    { max_wind: -1,    name: "溫帶氣旋",     color: "#DDDFE2" },
    { max_wind: 40,    name: "低壓區",       color: "#DDDFE2" },
    { max_wind: 62,    name: "熱帶低氣壓",   color: "#6DD8FA" },
    { max_wind: 87,    name: "熱帶風暴",     color: "#9DD79C" },
    { max_wind: 117,   name: "強烈熱帶風暴", color: "#FFD363" },
    { max_wind: 149,   name: "颱風",         color: "#F78A31" },
    { max_wind: 184,   name: "強颱風",       color: "#FF6F6F" },
    { max_wind: 9999,  name: "超強颱風",     color: "#DE82FF" }
];

function getTcIntensity(windKmh) {
    if (isNaN(windKmh)) return { name: "Ex / 未知", color: "#94a3b8" };
    const val = parseFloat(windKmh);
    for (let rule of TC_INTENSITY_TABLE) {
        if (val <= rule.max_wind) return rule;
    }
    return TC_INTENSITY_TABLE[TC_INTENSITY_TABLE.length - 1];
}

let allStormsData = {};
let currentViewMode = 'overview';

// 載入 A.csv 到 F.csv
async function loadAllStormTracks() {
    const files = ['A', 'B', 'C', 'D', 'E', 'F'];
    let loadedCount = 0;

    for (let prefix of files) {
        try {
            const response = await fetch(`TCdata/${prefix}.csv`);
            if (!response.ok) continue;
            const csvText = await response.text();
            const parsedData = parseCsvData(csvText);
            if (parsedData.length > 0) {
                allStormsData[prefix] = parsedData;
                loadedCount++;
            }
        } catch (e) {
            // 檔案不存在或網路錯誤則略過
        }
    }

    const loadingEl = document.getElementById('tcMapLoading');
    const wrapperEl = document.getElementById('tcMapCanvasWrapper');
    
    if (loadingEl) loadingEl.style.display = 'none';
    if (wrapperEl) wrapperEl.classList.remove('hidden');

    renderStormTracksUI();
}

// 解析 CSV 格式 (category,time,name,lat,lon,wind)
function parseCsvData(text) {
    const lines = text.trim().split('\n');
    const results = [];
    for (let i = 1; i < lines.length; i++) { // 跳過標題列
        const line = lines[i].trim();
        if (!line) continue;
        const parts = line.split(',');
        if (parts.length >= 6) {
            results.push({
                category: parts[0].trim(),
                time: parts[1].trim(),
                name: parts[2].trim(),
                lat: parseFloat(parts[3]),
                lon: parseFloat(parts[4]),
                wind: parts[5].trim()
            });
        }
    }
    return results;
}

// 渲染熱帶氣旋列表與路徑資訊
function renderStormTracksUI() {
    const container = document.getElementById('tcActiveStormsList');
    if (!container) return;
    
    container.innerHTML = '';
    const keys = Object.keys(allStormsData);

    if (keys.length === 0) {
        container.innerHTML = `<div class="col-span-full text-center text-slate-500 py-8">現時無發現任何熱帶氣旋路徑檔案 (TCdata/A~F.csv)。</div>`;
        return;
    }

    keys.forEach(prefix => {
        const track = allStormsData[prefix];
        // 尋找當前或最後一個點作為代表
        const currentPoint = track.slice().reverse().find(p => p.category === 'current') || track[track.length - 1];
        const stormName = track.find(p => p.name && p.name !== '')?.name || `氣旋 ${prefix}`;
        const intensity = getTcIntensity(currentPoint.wind);

        const card = document.createElement('div');
        card.className = "bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 rounded-xl shadow-sm space-y-2";
        card.innerHTML = `
            <div class="flex justify-between items-center">
                <span class="font-bold text-slate-800 dark:text-slate-100 text-sm flex items-center gap-1.5">
                    <i class="fa-solid fa-hurricane text-cyan-500"></i> ${stormName} (${prefix})
                </span>
                <span class="text-[10px] px-2 py-0.5 rounded font-semibold text-white" style="background-color: ${intensity.color};">${intensity.name}</span>
            </div>
            <div class="text-xs text-slate-500 dark:text-slate-400 space-y-1">
                <div>最新位置：${currentPoint.lat}°N, ${currentPoint.lon}°E</div>
                <div>風速強度：${currentPoint.wind} km/h</div>
                <div>時間：${currentPoint.time}</div>
            </div>
            <div class="text-[11px] text-cyan-600 dark:text-cyan-400 font-medium pt-1">
                總計追蹤點：${track.length} 個節點 (${currentViewMode === 'overview' ? '全域 5-50°N 範圍' : '單一氣旋聚焦'})
            </div>
        `;
        container.appendChild(card);
    });
}

// 切換地圖檢視模式
function switchTrackView(mode) {
    currentViewMode = mode;
    const btnOverview = document.getElementById('btn-overview');
    const btnZoom = document.getElementById('btn-zoom');
    
    if (mode === 'overview') {
        btnOverview.className = "px-3 py-1 text-xs bg-cyan-500 text-white rounded-xl shadow-sm transition-colors";
        btnZoom.className = "px-3 py-1 text-xs bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 rounded-xl shadow-sm transition-colors";
    } else {
        btnZoom.className = "px-3 py-1 text-xs bg-cyan-500 text-white rounded-xl shadow-sm transition-colors";
        btnOverview.className = "px-3 py-1 text-xs bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 rounded-xl shadow-sm transition-colors";
    }
    renderStormTracksUI();
}

// 頁面載入後自動執行載入
document.addEventListener('DOMContentLoaded', () => {
    loadAllStormTracks();
});
