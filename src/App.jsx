import { useEffect, useMemo, useRef, useState } from "react";
import { Chart } from "chart.js/auto";
import dayjs from "dayjs";
import isoWeek from "dayjs/plugin/isoWeek";
dayjs.extend(isoWeek);

// 서버 응답 제한 (너무 크면 1000~2000으로 조절)
const HUB = "/.netlify/functions/sheets-hub?limit=2000";

/* ================= 공통 유틸 ================= */
function useHubData() {
  const [data, setData] = useState({ items: [], loading: true, error: null });
  useEffect(() => {
    let alive = true;
    fetch(HUB)
      .then((r) => r.json())
      .then((j) => alive && setData({ items: j.items || [], loading: false, error: null }))
      .catch((e) => alive && setData({ items: [], loading: false, error: String(e) }));
    return () => { alive = false; };
  }, []);
  return data;
}

function filterRowsByDate(rows, dateCol, start, end) {
  if (!start && !end) return rows;
  return rows.filter((r) => {
    const d = dayjs(r[dateCol]);
    if (!d.isValid()) return false;
    if (start && d.isBefore(start, "day")) return false;
    if (end && d.isAfter(end, "day")) return false;
    return true;
  });
}

// 라벨/값 너무 많으면 등간격 샘플
function decimate(points, maxPoints = 800) {
  if (points.length <= maxPoints) return points;
  const step = Math.ceil(points.length / maxPoints);
  const out = [];
  for (let i = 0; i < points.length; i += step) out.push(points[i]);
  if (!out.length || out[out.length - 1] !== points[points.length - 1]) out.push(points[points.length - 1]);
  return out;
}

// 헤더에서 첫 매칭 컬럼
function findCol(headers, keywords) {
  const lower = headers.map((h) => (h || "").toLowerCase());
  for (let i = 0; i < lower.length; i++) {
    if (keywords.some((k) => lower[i].includes(k))) return i;
  }
  return -1;
}

function toBaseSeries(item, start, end, pickColIndex) {
  if (!item) return [];
  const dcol = item.dateCol ?? 0;
  const vcol = pickColIndex ?? (item.valueCols?.[0] ?? 1);
  const rows = filterRowsByDate(item.rows, dcol, start, end);
  const s = rows
    .map((r) => ({
      x: r[dcol],
      y: Number(String(r[vcol]).replace(/,/g, "")),
    }))
    .filter((p) => Number.isFinite(p.y));
  return s;
}

/* ===== 리샘플링: none / weekly / monthly (마지막 값 기준) ===== */
function resample(series, mode) {
  if (mode === "none") return series;
  const bucketMap = new Map(); // key -> {x,y} 마지막 값
  for (const p of series) {
    const d = dayjs(p.x);
    if (!d.isValid()) continue;
    let key;
    if (mode === "weekly") {
      key = `${d.isoWeekYear()}-W${String(d.isoWeek()).padStart(2, "0")}`;
      // 대표 날짜는 주 마지막 날로
      const end = d.isoWeekYear() === d.add(6 - (d.isoWeekday() - 1), "day").isoWeekYear()
        ? d.add(6 - (d.isoWeekday() - 1), "day")
        : d.endOf("week");
      bucketMap.set(key, { x: end.format("YYYY-MM-DD"), y: p.y });
    } else if (mode === "monthly") {
      key = d.format("YYYY-MM");
      bucketMap.set(key, { x: d.endOf("month").format("YYYY-MM-DD"), y: p.y });
    }
  }
  const out = Array.from(bucketMap.values()).sort((a, b) => (a.x < b.x ? -1 : 1));
  return out;
}

function buildSeries(item, start, end, pickColIndex, mode = "none") {
  const base = toBaseSeries(item, start, end, pickColIndex);
  const sampled = resample(base, mode);
  return decimate(sampled, 800);
}

/* ================= 차트 ================= */
function LineChart({ series, label, yAxis = "y" }) {
  const ref = useRef(null);
  const chartRef = useRef(null);

  // y축 범위를 데이터 기반으로 강제
  const [min, max] = useMemo(() => {
    if (!series || !series.length) return [0, 1];
    let mn = Infinity, mx = -Infinity;
    for (const p of series) { if (p.y < mn) mn = p.y; if (p.y > mx) mx = p.y; }
    if (!Number.isFinite(mn) || !Number.isFinite(mx)) return [0, 1];
    if (mn === mx) { mn -= 1; mx += 1; }     // 평평하면 범위 확보
    const pad = (mx - mn) * 0.05;            // 5% 여백
    return [mn - pad, mx + pad];
  }, [series]);

  useEffect(() => {
    if (!ref.current) return;
    const ctx = ref.current.getContext("2d");
    if (chartRef.current) chartRef.current.destroy();

    if (!series || series.length === 0) {
      ref.current.replaceWith(ref.current.cloneNode(true)); // 캔버스 리셋
      return;
    }

    chartRef.current = new Chart(ctx, {
      type: "line",
      data: {
        labels: series.map((p) => p.x),
        datasets: [{ label, data: series.map((p) => p.y), yAxisID: yAxis }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        parsing: false,
        scales: {
          x: { ticks: { maxRotation: 0, autoSkip: true } },
          [yAxis]: { position: yAxis === "y1" ? "right" : "left", suggestedMin: min, suggestedMax: max },
          ...(yAxis === "y" ? { y1: { position: "right", grid: { drawOnChartArea: false } } } : {}),
        },
        elements: { line: { spanGaps: true } },
      },
    });
    return () => chartRef.current?.destroy();
  }, [series, label, yAxis, min, max]);

  if (!series || series.length === 0) {
    return (
      <div style={{
        height: 300, display: "flex", alignItems: "center", justifyContent: "center",
        color: "#888", fontSize: 14, border: "1px dashed #ddd", borderRadius: 8
      }}>
        데이터 없음
      </div>
    );
  }
  return <canvas ref={ref} style={{ width: "100%", height: 300 }} />;
}

/* ================= 메인 ================= */
export default function App() {
  const { items, loading, error } = useHubData();

  const [start, setStart] = useState(() => dayjs("2021-01-01").format("YYYY-MM-DD"));
  const [end, setEnd] = useState(() => dayjs().format("YYYY-MM-DD"));

  // 리샘플링: none / weekly / monthly
  const [sampleMode, setSampleMode] = useState("none");

  // 종목용 토글: close | volume | rsi
  const [equityMode, setEquityMode] = useState("close");

  const allOk = useMemo(() => items.filter((it) => !it.error), [items]);
  const metrics = useMemo(() => allOk.filter((it) => it.type === "metric"), [allOk]);
  const equities = useMemo(() => allOk.filter((it) => it.type === "equity"), [allOk]);

  // RSI 별도 시트 매핑(005930_RSI -> 005930)
  const rsiMap = useMemo(() => {
    const m = new Map();
    for (const it of allOk) {
      const k = String(it.key || "");
      if (/_rsi$/i.test(k) || /rsi/.test((it.title || "").toLowerCase())) {
        m.set(k.replace(/_rsi$/i, ""), it);
      }
    }
    return m;
  }, [allOk]);

  // 종목 카드별 시리즈
  function equitySeries(item) {
    if (!item) return { label: item?.title || item?.key, series: [] };
    const headers = item.headers || [];

    if (equityMode === "volume") {
      const idx = findCol(headers, ["volume", "거래"]);
      const s = buildSeries(item, start, end, idx >= 0 ? idx : undefined, sampleMode);
      return { label: `${item.title || item.key} (Volume)`, series: s };
    }
    if (equityMode === "rsi") {
      const idx = findCol(headers, ["rsi", "rsi14"]);
      if (idx >= 0) {
        return { label: `${item.title || item.key} (RSI)`, series: buildSeries(item, start, end, idx, sampleMode) };
      }
      const alt = rsiMap.get(String(item.key));
      if (alt) {
        const idx2 = findCol(alt.headers || [], ["rsi", "rsi14", "value", "close"]);
        return { label: `${item.title || item.key} (RSI)`, series: buildSeries(alt, start, end, idx2 >= 0 ? idx2 : undefined, sampleMode) };
      }
      return { label: `${item.title || item.key} (Close*)`, series: buildSeries(item, start, end, undefined, sampleMode) };
    }

    const idx = findCol(headers, ["close", "price", "adj close", "value"]);
    return { label: `${item.title || item.key}`, series: buildSeries(item, start, end, idx >= 0 ? idx : undefined, sampleMode) };
  }

  if (loading) return <div style={{ padding: 24 }}>Loading…</div>;
  if (error) return <div style={{ padding: 24, color: "crimson" }}>{error}</div>;

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: 16 }}>
      <h1 style={{ fontSize: 24, marginBottom: 8 }}>Finance Dashboard</h1>

      {/* 기간 & 리샘플링 */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
        <label>시작일&nbsp;<input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></label>
        <label>종료일&nbsp;<input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></label>
        <button onClick={() => { setStart("2021-01-01"); setEnd(dayjs().format("YYYY-MM-DD")); }}>기본 기간</button>
        <label>리샘플링&nbsp;
          <select value={sampleMode} onChange={(e) => setSampleMode(e.target.value)}>
            <option value="none">원본(일별)</option>
            <option value="weekly">주별(마지막 값)</option>
            <option value="monthly">월별(마지막 값)</option>
          </select>
        </label>
      </div>

      {/* ===== Macro Metrics ===== */}
      {metrics.length > 0 && (
        <>
          <h2 style={{ fontSize: 20, margin: "16px 0 8px" }}>Macro Metrics</h2>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
            {metrics.map((item) => {
              const s = buildSeries(item, start, end, undefined, sampleMode);
              return (
                <div key={item.key} style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12 }}>
                  <div style={{ fontWeight: 600, marginBottom: 8 }}>{item.title || item.key}</div>
                  <LineChart label={item.title || item.key} series={s} />
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* ===== Equities (Close/Volume/RSI) ===== */}
      {equities.length > 0 && (
        <>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 24 }}>
            <h2 style={{ fontSize: 20, margin: "0 0 8px 0" }}>Equities</h2>
            <div style={{ display: "flex", gap: 8 }}>
              <label><input type="radio" name="emode" value="close"
                checked={equityMode === "close"} onChange={(e) => setEquityMode(e.target.value)} /> Close</label>
              <label><input type="radio" name="emode" value="volume"
                checked={equityMode === "volume"} onChange={(e) => setEquityMode(e.target.value)} /> Volume</label>
              <label><input type="radio" name="emode" value="rsi"
                checked={equityMode === "rsi"} onChange={(e) => setEquityMode(e.target.value)} /> RSI</label>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
            {equities.map((item) => {
              const { label, series } = equitySeries(item);
              return (
                <div key={item.key} style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12 }}>
                  <div style={{ fontWeight: 600, marginBottom: 8 }}>{label}</div>
                  <LineChart label={label} series={series} />
                </div>
              );
            })}
          </div>
        </>
      )}

      {(metrics.length === 0 && equities.length === 0) && (
        <div style={{ color: "#666", marginTop: 16 }}>
          INDEX에 등록된 시리즈가 없습니다. INDEX 탭에 type/key/title/csv_url을 추가해 주세요.
        </div>
      )}
    </div>
  );
}
