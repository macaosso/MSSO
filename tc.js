const tcText = `預料高空反氣旋於未來兩日將持續影響廣東沿岸，天色仍以天晴為主及日間酷熱。

展望下週初風力微弱，高空擾動將為本澳帶來幾陣驟雨及雷暴；隨後轉受偏東氣流影響，驟雨逐漸減少。`;

const tcWarnings = `熱帶氣旋「沙德爾」正逐漸逼近華南沿岸，本澳氣象部門正密切監察其動向。

氣象局將視乎其與本澳的距離及強度變化，在適當時機評估並考慮發出相關風暴信號。

請廣大市民提前做好各項防風及低窪地區防水浸準備，並隨時留意本台發佈的最新天氣消息。`;

const TC_WARNING_DATA = {
  mainTitle: "受熱帶氣旋「沙德爾」可能發佈之警報",
  updateTimeText: "2026-09-02  14:20 MST 更新",
  tableRows: [
    { signal: "注意警報", period: "", probability: "" },
    { signal: "戒備警報", period: "09月02日 14時20分", probability: "" },
    { signal: "強風警報", period: "09月04日 日間", probability: "" },
    { signal: "烈風警報", period: "09月01日", probability: "" },
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
