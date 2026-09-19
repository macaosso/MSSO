const tcText = `下午2時，強烈熱帶風暴杜鵑集結在本澳東北偏東2700公里，預料向西北移動，時速約15公里，橫過日本以南海域。`;

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
