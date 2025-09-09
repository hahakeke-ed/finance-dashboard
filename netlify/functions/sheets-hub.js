/** Minimal CSV parser (handles quotes) */
function parseCsv(text) {
  const rows = [];
  let i = 0, field = '', inQuotes = false, row = [];
  while (i < text.length) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; }
        else inQuotes = false;
      } else field += c;
    } else {
      if (c === '"') inQuotes = true;
      else if (c === ',') { row.push(field); field = ''; }
      else if (c === '\n') { row.push(field); rows.push(row); field = ''; row = []; }
      else if (c === '\r') { /* ignore */ }
      else field += c;
    }
    i++;
  }
  if (field.length || row.length) { row.push(field); rows.push(row); }
  return rows;
}

function csvToTable(text) {
  const rows = parseCsv(text);
  if (!rows.length) return { headers: [], rows: [] };
  // 기본 트림 + BOM 제거
  const headers = rows[0].map(h => String(h || '').replace(/^\uFEFF/, '').trim());
  const data = rows.slice(1).filter(r => r.some(x => String(x).trim() !== ''));
  return { headers, rows: data };
}

// 헤더 정규화: 소문자, BOM 제거, 공백/밑줄 제거
const norm = (s) =>
  String(s || '')
    .replace(/\uFEFF/g, '')
    .toLowerCase()
    .replace(/[\s_]+/g, '');

/** 날짜 컬럼 위치 추정 */
function findDateCol(headers) {
  const idx = headers.findIndex(h => /date|time/i.test(h));
  return idx >= 0 ? idx : 0;
}

/** 대표 숫자 컬럼 후보 */
function numericCols(headers) {
  const wanted = ['value', 'close', 'adj close', 'price', 'volume', 'rsi', 'rsi14', 'open', 'high', 'low'];
  const idxs = [];
  headers.forEach((h, i) => {
    if (wanted.some(w => h.toLowerCase().includes(w))) idxs.push(i);
  });
  return idxs.length ? idxs : headers.map((_, i) => i).slice(1);
}

export const handler = async (event) => {
  try {
    const INDEX_CSV = process.env.INDEX_CSV;
    if (!INDEX_CSV) {
      return {
        statusCode: 500,
        headers: { 'content-type': 'application/json', 'access-control-allow-origin': '*' },
        body: JSON.stringify({ error: 'Missing INDEX_CSV env var.' })
      };
    }

    const idxText = await (await fetch(INDEX_CSV)).text();
    const { headers: hIdx, rows: rIdx } = csvToTable(idxText);

    // 요구 헤더: type, key, title, csv_url  (공백/밑줄/대소문자/ BOM 무시)
    const need = ['type','key','title','csv_url'];
    const idxMap = {};
    need.forEach((name) => {
      const pos = hIdx.findIndex(h => norm(h) === norm(name)); // <-- 핵심
      idxMap[name] = pos;
    });

    if (need.some(n => idxMap[n] < 0)) {
      return {
        statusCode: 400,
        headers: { 'content-type': 'application/json', 'access-control-allow-origin': '*' },
        body: JSON.stringify({
          error: `INDEX CSV must have headers: type,key,title,csv_url`,
          receivedHeaders: hIdx
        })
      };
    }

    const params = event.queryStringParameters || {};
    const typeFilter = params.type && params.type.toLowerCase();
    const keysFilter = params.keys ? new Set(params.keys.split(',').map(s=>s.trim())) : null;

    const items = [];
    for (const r of rIdx) {
      const type  = (r[idxMap['type']]  || '').trim();
      const key   = (r[idxMap['key']]   || '').trim();
      const title = (r[idxMap['title']] || '').trim();
      const url   = (r[idxMap['csv_url']]   || '').trim();
      if (!type || !key || !url) continue;
      if (typeFilter && type.toLowerCase() !== typeFilter) continue;
      if (keysFilter && !keysFilter.has(key)) continue;

      try {
        const csvText = await (await fetch(url)).text();
        const { headers, rows } = csvToTable(csvText);
        const dateCol = findDateCol(headers);
        const valueCols = numericCols(headers);
        items.push({ type, key, title, headers, dateCol, valueCols, rows });
      } catch (e) {
        items.push({ type, key, title, error: String(e) });
      }
    }

    return {
      statusCode: 200,
      headers: { 'content-type': 'application/json', 'access-control-allow-origin': '*' },
      body: JSON.stringify({ updatedAt: new Date().toISOString(), items }, null, 2)
    };
  } catch (e) {
    return {
      statusCode: 500,
      headers: { 'content-type': 'application/json', 'access-control-allow-origin': '*' },
      body: JSON.stringify({ error: String(e) })
    };
  }
};
