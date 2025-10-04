let map;
let heatmapLayer = null;
let circleMarkers = [];
let currentRows = [];
let parameterColumns = [];
let timeValues = [];

const DEFAULT_CENTER = { lat: -23.55052, lng: -46.633308 }; // São Paulo

function initMap() {
  map = new google.maps.Map(document.getElementById('map'), {
    center: DEFAULT_CENTER,
    zoom: 9,
    mapTypeControl: true,
    streetViewControl: false
  });

  const csvUrlInput = document.getElementById('csvUrl');
  csvUrlInput.value = '../data/saopaulo_20251001_20251002_0p05deg.csv';
  document.getElementById('loadBtn').addEventListener('click', () => {
    const url = csvUrlInput.value.trim();
    if (!url) return;
    loadCsv(url);
  });

  document.getElementById('parameterSelect').addEventListener('change', render);
  document.getElementById('timeSelect').addEventListener('change', render);
  document.getElementById('viewMode').addEventListener('change', render);
}

async function loadCsv(url) {
  clearLayers();
  const parsed = await parseCsv(url);
  const { data, meta } = parsed;
  currentRows = data.filter(Boolean);

  // Identify columns
  const headers = meta.fields || Object.keys(currentRows[0] || {});
  const latKey = findHeader(headers, ['lat', 'latitude']);
  const lonKey = findHeader(headers, ['lon', 'lng', 'longitude']);
  const timeKey = findHeader(headers, ['validdate', 'date', 'time']);

  if (!latKey || !lonKey || !timeKey) {
    alert('Could not infer lat/lon/time columns from CSV.');
    return;
  }

  // Parameter columns are everything that's not lat/lon/time
  parameterColumns = headers.filter(h => ![latKey, lonKey, timeKey].includes(h));
  timeValues = Array.from(new Set(currentRows.map(r => r[timeKey]))).sort();

  // Render UI options
  const paramSel = document.getElementById('parameterSelect');
  paramSel.innerHTML = '';
  parameterColumns.forEach((p, i) => {
    const opt = document.createElement('option');
    opt.value = p; opt.textContent = p; if (i === 0) opt.selected = true;
    paramSel.appendChild(opt);
  });

  const timeSel = document.getElementById('timeSelect');
  timeSel.innerHTML = '';
  timeValues.forEach((t, i) => {
    const opt = document.createElement('option');
    opt.value = t; opt.textContent = t; if (i === 0) opt.selected = true;
    timeSel.appendChild(opt);
  });

  // Store keys for rendering
  map.__latKey = latKey;
  map.__lonKey = lonKey;
  map.__timeKey = timeKey;

  render();
}

function parseCsv(url) {
  return new Promise((resolve, reject) => {
    Papa.parse(url, {
      download: true,
      header: true,
      dynamicTyping: true,
      skipEmptyLines: true,
      complete: results => resolve(results),
      error: err => reject(err)
    });
  });
}

function findHeader(headers, candidates) {
  const lower = headers.map(h => ({ key: h, lower: String(h).toLowerCase() }));
  for (const cand of candidates) {
    const hit = lower.find(h => h.lower.includes(cand));
    if (hit) return hit.key;
  }
  return null;
}

function render() {
  clearLayers();
  if (!currentRows.length) return;
  const param = document.getElementById('parameterSelect').value;
  const ts = document.getElementById('timeSelect').value;
  const mode = document.getElementById('viewMode').value;

  const latKey = map.__latKey, lonKey = map.__lonKey, timeKey = map.__timeKey;
  const rows = currentRows.filter(r => String(r[timeKey]) === String(ts));

  const values = rows.map(r => Number(r[param])).filter(v => Number.isFinite(v));
  const vmin = Math.min(...values);
  const vmax = Math.max(...values);

  updateLegend(param, vmin, vmax);

  if (mode === 'heatmap') {
    const heatData = rows.map(r => {
      const val = Number(r[param]);
      const weight = normalize(val, vmin, vmax);
      return { location: new google.maps.LatLng(r[latKey], r[lonKey]), weight };
    }).filter(e => Number.isFinite(e.weight));
    heatmapLayer = new google.maps.visualization.HeatmapLayer({ data: heatData, radius: 16, dissipating: true });
    heatmapLayer.setMap(map);
  } else {
    for (const r of rows) {
      const val = Number(r[param]);
      if (!Number.isFinite(val)) continue;
      const color = colorRamp(normalize(val, vmin, vmax));
      const marker = new google.maps.Circle({
        strokeOpacity: 0,
        fillColor: color,
        fillOpacity: 0.7,
        radius: 300,
        map,
        center: { lat: Number(r[latKey]), lng: Number(r[lonKey]) }
      });
      circleMarkers.push(marker);
    }
  }
}

function clearLayers() {
  if (heatmapLayer) { heatmapLayer.setMap(null); heatmapLayer = null; }
  for (const m of circleMarkers) m.setMap(null);
  circleMarkers = [];
}

function normalize(v, a, b) {
  if (!Number.isFinite(v)) return 0;
  if (a === b) return 0.5;
  return (v - a) / (b - a);
}

function colorRamp(t) {
  // Blues -> light -> yellow -> orange -> red
  const stops = [
    [44, 123, 182],   // #2c7bb6
    [171, 217, 233],  // #abd9e9
    [255, 255, 191],  // #ffffbf
    [253, 174, 97],   // #fdae61
    [215, 25, 28]     // #d7191c
  ];
  const scaled = Math.min(Math.max(t, 0), 1) * (stops.length - 1);
  const i = Math.floor(scaled);
  const f = scaled - i;
  const c0 = stops[i];
  const c1 = stops[Math.min(i + 1, stops.length - 1)];
  const r = Math.round(c0[0] + (c1[0] - c0[0]) * f);
  const g = Math.round(c0[1] + (c1[1] - c0[1]) * f);
  const b = Math.round(c0[2] + (c1[2] - c0[2]) * f);
  return `rgb(${r}, ${g}, ${b})`;
}

function updateLegend(param, vmin, vmax) {
  const legend = document.getElementById('legend');
  legend.innerHTML = '';
  const h2 = document.createElement('h2');
  h2.textContent = param;
  legend.appendChild(h2);
  const bar = document.createElement('div');
  bar.className = 'colorbar';
  legend.appendChild(bar);
  const row = document.createElement('div');
  row.className = 'legend-row';
  row.innerHTML = `<span>${vmin.toFixed(3)}</span><span>${vmax.toFixed(3)}</span>`;
  legend.appendChild(row);
}


