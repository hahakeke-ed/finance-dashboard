import { useEffect, useMemo, useRef, useState } from "react";
import { Chart } from "chart.js/auto";
import dayjs from "dayjs";

// ★ 필요하면 서버 응답을 가볍게: 뒤에 "?limit=2000" 같은 파라미터를 붙일 수 있어요.
const HUB = "/.netlify/functions/sheets-hub?limit=2000";

function useHubData() {
  const [data, setData] = useState({ items: [], loading: true, error: null });
  useEffect(() => {
    let alive = true;
    fetch(HUB)
      .then(r => r.json())
      .then(json => { if (alive) setData({ items: json.items || [], loading: false, error: null }); })
      .catch(err => { if (alive) setData({ items: [], loading: false, error: String(err) }); });
    return () => { alive = false; };
  }, []);
  return data;
}

function filterRowsByDate(rows, dateCol, start, end) {
  if (!start && !end) return rows;
  return rows.filter(r => {
    const d = dayjs(r[dateCol]);
    if (!d.isValid()) return false;
    if (start && d.isBefore(start, "day")) return false;
    if (end && d.isAfter(end, "day")) return false;
    return true;
  });
}

function LineChart({ series, label }) {
  const ref = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    const ctx = ref.current.getContext("2d");
    if (chartRef.current) chartRef.current.destroy();
    chartRef.current = new Chart(ctx, {
      type: "line",
      data: {
        labels: series.map(p => p.x),
        datasets: [{ label, data: series.map(p => p.y) }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        parsing: false,
        normalized: true,
        scales: { x: { ticks: { maxRotation: 0 } } }
      }
    });
    return () => chartRef.current?.destroy();
  }, [series, label]);

  return <canvas ref={ref} style={{ width: "100%", height: 300 }} />;
}

export default function App() {
  const { items, loading, error } = useHubData();

  // ★ 기본값: 시작=2021-01-01, 종료=오늘
  const [start, setStart] = useState(() => dayjs("2021-01-01").format("YYYY-MM-DD"));
  const [end, setEnd] = useState(() => dayjs().format("YYYY-MM-DD"));

  // type별로 구분(보기만)
  const metrics = useMemo(() => items.filter(it => it.type === "metric" && !it.error), [items]);
  const equities = useMemo(() => items.filter(it => it.type === "equity" && !it.error), [items]);

  // 공통 변환 함수: 각 item을 기간 필터링 후 시리즈로 변환
  const toSeries = (item) => {
    if (!item) return [];
    const dcol = item.dateCol ?? 0;
    const vcol = (item.valueCols && item.valueCols[0]) ?? 1; // 대표값(첫 번째 숫자 컬럼)
    const rows = filterRowsByDate(item.rows, dcol, start || null, end || null);
    return rows.map(r => ({
      x: r[dcol],
      y: Number(String(r[vcol]).replace(/,/g, "")) || null
    })).filter(p => p.y != null);
  };

  if (loading) return <div style={{ padding: 24 }}>Loading…</div>;
  if (error) return <div style={{ padding: 24, color: "crimson" }}>{error}</div>;

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: 16 }}>
      <h1 style={{ fontSize: 24, marginBottom: 8 }}>Finance Dashboard</h1>

      {/* 기간 필터 */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
        <label>시작일&nbsp;
          <input type="date" value={start} onChange={e => setStart(e.target.value)} />
        </label>
        <label>종료일&nbsp;
          <input type="date" value={end} onChange={e => setEnd(e.target.value)} />
        </label>
        <button onClick={() => { setStart("2021-01-01"); setEnd(dayjs().format("YYYY-MM-DD")); }}>
          기본 기간(2021-01-01 ~ 오늘)
        </button>
      </div>

      {/* 모든 지표 차트 */}
      {metrics.length > 0 && (
        <>
          <h2 style={{ fontSize: 20, margin: "16px 0 8px" }}>Macro Metrics</h2>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            {metrics.map(item => (
              <div key={item.key} style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12 }}>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>{item.title || item.key}</div>
                <LineChart label={item.title || item.key} series={toSeries(item)} />
              </div>
            ))}
          </div>
        </>
      )}

      {/* 모든 종목 차트 */}
      {equities.length > 0 && (
        <>
          <h2 style={{ fontSize: 20, margin: "24px 0 8px" }}>Equities</h2>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            {equities.map(item => (
              <div key={item.key} style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12 }}>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>{item.title || item.key}</div>
                <LineChart label={item.title || item.key} series={toSeries(item)} />
              </div>
            ))}
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
