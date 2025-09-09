import { useEffect, useMemo, useRef, useState } from "react";
import { Chart } from "chart.js/auto";
import dayjs from "dayjs";

// ★ 응답 크기 제한 (권장)
const HUB = "/.netlify/functions/sheets-hub?limit=1500";

/* -------------------- 공통 유틸 -------------------- */
function useHubData() {
  const [data, setData] = useState({ items: [], loading: true, error: null });
  useEffect(() => {
    let alive = true;
    fetch(HUB)
      .then((r) => r.json())
      .then((json) => alive && setData({ items: json.items || [], loading: false, error: null }))
      .catch((err) => alive && setData({ items: [], loading: false, error: String(err) }));
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

// 너무 많은 포인트일 때 간단 다운샘플링 (균등 간격 샘플)
function decimate(points, maxPoints = 800) {
  if (points.length <= maxPoints) return points;
  const step = Math.ceil(points.length / maxPoints);
  const out = [];
  for (let i = 0; i < points.length; i += step) out.push(points[i]);
  if (out[out.length - 1] !== points[points.length - 1]) out.push(points[points.length - 1]);
  return out;
}

// 특정 헤더 포함 컬럼 탐색
function findCol(headers, keywords) {
  const lower = headers.map((h) => (h || "").toLowerCase());
  for (let i = 0; i < lower.length; i++) {
    if (keywords.some((k) => lower[i].includes(k))) return i;
  }
  return -1;
}

function toSeries(item, start, end, pickColIndex) {
  if (!item) return [];
  const dcol = item.dateCol ?? 0;
  const vcol = pickColIndex ?? (item.valueCols?.[0] ?? 1);
  const rows = filterRowsByDate(item.rows, dcol, start, end);
  const series = rows
    .map((r) => ({
      x: r[dcol],
      y: Number(String(r[vcol]).replace(/,/g, "")),
    }))
    .filter((p) => Number.isFinite(p.y));
  return decimate(series, 800);
}

/* -------------------- 차트 컴포넌트 -------------------- */
function LineChart({ series, label, yAxis = "y" }) {
  const ref = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    if (!ref.current) return;
    const ctx = ref.current.getContext("2d");
    if (chartRef.current) chartRef.current.destroy();

    // 시리즈가 비었으면 렌더하지 않음
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
        // normalized: true  // <-- ❌ 축이 0~1로 보일 수 있어 제거
        scales: {
          x: { ticks: { maxRotation: 0, autoSkip: true } },
          y: { position: "left" },
          y1: { position: "right", grid: { drawOnChartArea: false } },
        },
        elements: { line: { spanGaps: true } },
      },
    });
    return () => chartRef.current?.destroy();
  }, [series, label, yAxis]);

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

/* -------------------- 페이지 -------------------- */
export default function App() {
  const { items, loading, error } = useHubData();

  const [start, setStart] = useState(() => dayjs("2021-01-01").format("YYYY-MM-DD"));
  const [end, setEnd] = useState(() => dayjs().format("YYYY-MM-DD"));

  const [equityMode, setEquityMode] = useState("close");

  const allOkItems = items.filter((it) => !it.error);
  const metrics = useMemo(() => items.filter((it) => it.type === "metric" && !it.error), [items]);
  const equities = useMemo(() => items.filter((it) => it.type === "equity" && !it.error), [items]);

  // RSI 별도 시트 매핑 (예: 005930_RSI)
  const rsiMap = useMemo(() => {
    const map = new Map();
    for (const it of allOkItems) {
      const k = String(it.key || "");
      if (/_rsi$/i.test(k) || /rsi/.test(it.title?.toLowerCase() || "")) {
        map.set(k.replace(/_rsi$/i, ""), it);
      }
    }
    return map;
  }, [allOkItems]);

  function equitySeriesByMode(item) {
    if (!item) return { label: item?.title || item?.key, series: [] };
    const headers = item.headers || [];

    if (equityMode === "volume") {
      const volIdx = findCol(headers, ["volume", "거래"]);
      const s = toSeries(item, start, end, volIdx >= 0 ? volIdx : undefined);
      return { label: `${item.title || item.key} (Volume)`, series: s };
    }
    if (equityMode === "rsi") {
      const rsiIdx = findCol(headers, ["rsi", "rsi14"]);
      if (rsiIdx >= 0) {
        return { label: `${item.title || item.key} (RSI)`, series: toSeries(item, start, end, rsiIdx) };
      }
      const alt = rsiMap.get(String(item.key));
      if (alt) {
        const rsiIdx2 = findCol(alt.headers || [], ["rsi", "rsi14", "value", "close"]);
        return { label: `${item.title || item.key} (RSI)`, series: toSeries(alt, start, end, rsiIdx2 >= 0 ? rsiIdx2 : undefined) };
      }
      return { label: `${item.title || item.key} (Close*)`, series: toSeries(item, start, end) };
    }
    const closeIdx = findCol(headers, ["close", "price", "adj close", "value"]);
    return { label: `${item.title || item.key}`, series: toSeries(item, start, end, closeIdx >= 0 ? closeIdx : undefined) };
  }

  // 2축 겹쳐보기 (왼/오른쪽 선택은 생략 – 느려짐 방지를 위해 필요 시 나중에 다시 활성화)
  // 여기서는 우선 전체 카드 렌더에 집중

  /* -------------------- 렌더 -------------------- */
  if (loading) return <div style={{ padding: 24 }}>Loading…</div>;
  if (error) return <div style={{ padding: 24, color: "crimson" }}>{error}</div>;

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: 16 }}>
      <h1 style={{ fontSize: 24, marginBottom: 8 }}>Finance Dashboard</h1>

      {/* 기간 필터 */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
        <label>시작일&nbsp;
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label>종료일&nbsp;
          <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
        <button onClick={() => { setStart("2021-01-01"); setEnd(dayjs().format("YYYY-MM-DD")); }}>
          기본 기간(2021-01-01 ~ 오늘)
        </button>
      </div>

      {/* ===== Macro Metrics ===== */}
      {metrics.length > 0 && (
        <>
          <h2 style={{ fontSize: 20, margin: "16px 0 8px" }}>Macro Metrics</h2>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
            {metrics.map((item) => {
              const s = toSeries(item, start, end);
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

      {/* ===== Equities (Close/Volume/RSI 토글) ===== */}
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
              const { label, series } = equitySeriesByMode(item);
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
