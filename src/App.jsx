import { useEffect, useMemo, useRef, useState } from "react";
import { Chart } from "chart.js/auto";
import dayjs from "dayjs";

const HUB = "/.netlify/functions/sheets-hub";

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

  return <canvas ref={ref} style={{ width: "100%", height: 360 }} />;
}

export default function App() {
  const { items, loading, error } = useHubData();

  const metrics = items.filter(it => it.type === "metric" && !it.error);
  const equities = items.filter(it => it.type === "equity" && !it.error);

  const [activeType, setActiveType] = useState("metric");
  const pool = activeType === "metric" ? metrics : equities;
  const [activeKey, setActiveKey] = useState(pool[0]?.key);
  useEffect(() => { if (pool.length && !pool.find(x => x.key === activeKey)) setActiveKey(pool[0]?.key); }, [activeType, items]);

  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const current = pool.find(x => x.key === activeKey);

  const series = useMemo(() => {
    if (!current) return [];
    const dcol = current.dateCol ?? 0;
    const vcol = (current.valueCols && current.valueCols[0]) ?? 1;
    const rows = filterRowsByDate(current.rows, dcol, start || null, end || null);
    return rows.map(r => ({
      x: r[dcol],
      y: Number(String(r[vcol]).replace(/,/g, "")) || null
    })).filter(p => p.y != null);
  }, [current, start, end]);

  if (loading) return <div style={{ padding: 24 }}>Loading…</div>;
  if (error) return <div style={{ padding: 24, color: "crimson" }}>{error}</div>;

  return (
    <div style={{ maxWidth: 1080, margin: "0 auto", padding: 16 }}>
      <h1 style={{ fontSize: 24, marginBottom: 8 }}>Finance Dashboard</h1>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <select value={activeType} onChange={e => setActiveType(e.target.value)}>
          <option value="metric">Macro Metrics</option>
          <option value="equity">Equities</option>
        </select>

        <select value={activeKey} onChange={e => setActiveKey(e.target.value)}>
          {pool.map(it => (
            <option key={it.key} value={it.key}>{it.title || it.key}</option>
          ))}
        </select>

        <label>시작일 <input type="date" value={start} onChange={e => setStart(e.target.value)} /></label>
        <label>종료일 <input type="date" value={end} onChange={e => setEnd(e.target.value)} /></label>
        <button onClick={() => { setStart(""); setEnd(""); }}>기간 초기화</button>
      </div>

      <div style={{ marginTop: 16, border: "1px solid #ddd", borderRadius: 8, padding: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>
          {current?.title || current?.key}
        </div>
        <LineChart label={current?.title || current?.key} series={series} />
      </div>

      <p style={{ color: "#666", marginTop: 12 }}>
        * INDEX 탭에서 줄을 추가/삭제하면 다음 호출에 자동 반영됩니다.
      </p>
    </div>
  );
}
