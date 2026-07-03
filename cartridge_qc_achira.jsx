import { useState } from "react";

// ── Real dimensions extracted from DWG ACMCTA001 (Achira Beta Cartridge, PMMA) ──
const FEATURES = [
  // ── OVERALL BODY (Sheet 1) ──
  { id: "OB01", group: "Overall Body",    desc: "Overall length",           nominal: 74.00, tol_lo: -0.05, tol_hi: 0.00,  unit: "mm", method: "Edge-to-edge", sheet: 1, priority: "High" },
  { id: "OB02", group: "Overall Body",    desc: "Overall width",            nominal: 40.00, tol_lo: -0.05, tol_hi: 0.00,  unit: "mm", method: "Edge-to-edge", sheet: 1, priority: "High" },
  { id: "OB03", group: "Overall Body",    desc: "Corner radius (top)",      nominal: 4.15,  tol_lo: 0.00,  tol_hi: 0.05,  unit: "mm", method: "Circle fit", sheet: 1, priority: "Medium" },
  { id: "OB04", group: "Overall Body",    desc: "Corner radius (bottom)",   nominal: 5.65,  tol_lo: 0.00,  tol_hi: 0.05,  unit: "mm", method: "Circle fit", sheet: 1, priority: "Medium" },
  { id: "OB05", group: "Overall Body",    desc: "Side corner radii (2x)",   nominal: 5.00,  tol_lo: 0.00,  tol_hi: 0.05,  unit: "mm", method: "Circle fit", sheet: 1, priority: "Medium" },
  { id: "OB06", group: "Overall Body",    desc: "Draft angle",              nominal: 2.00,  tol_lo: 0.00,  tol_hi: 0.00,  unit: "°",  method: "Angular meas.", sheet: 1, priority: "Low" },

  // ── CHANNEL / SECTION A-A + DETAIL K (Sheets 1 & 5) — depth features excluded ──
  // Detail K (Scale 8:1, Sheet 5) confirms the neck geometry precisely
  { id: "CH02", group: "Channel",         desc: "Channel width (typ)",               nominal: 3.20,  tol_lo: 0.00,  tol_hi: 0.05,  unit: "mm", method: "Min wall distance", sheet: 1, priority: "High" },
  { id: "CH03", group: "Channel",         desc: "Channel rib width (typ)",           nominal: 1.49,  tol_lo: 0.00,  tol_hi: 0.02,  unit: "mm", method: "Edge measurement", sheet: 1, priority: "High" },
  { id: "CH04", group: "Channel",         desc: "Wide channel into neck (Detail K)", nominal: 0.60,  tol_lo: 0.00,  tol_hi: 0.02,  unit: "mm", method: "Perpendicular wall distance", sheet: 5, priority: "Critical" },
  { id: "CH05", group: "Channel",         desc: "Neck constriction width (Detail K)",nominal: 0.20,  tol_lo: 0.00,  tol_hi: 0.02,  unit: "mm", method: "Min perpendicular wall distance", sheet: 5, priority: "Critical" },
  { id: "CH06", group: "Channel",         desc: "Neck constriction angle (Detail K)",nominal: 90.00, tol_lo: 0.00,  tol_hi: 0.00,  unit: "°",  method: "Angular meas. at constriction", sheet: 5, priority: "Medium" },
  { id: "CH07", group: "Channel",         desc: "Neck funnel radius (2×R1.20)",      nominal: 1.20,  tol_lo: -0.05, tol_hi: 0.00,  unit: "mm", method: "Circle fit at funnel wall", sheet: 5, priority: "Medium" },
  { id: "CH08", group: "Channel",         desc: "Neck slot length (Detail K)",       nominal: 3.25,  tol_lo: -0.02, tol_hi: 0.00,  unit: "mm", method: "Edge-to-edge along centerline", sheet: 5, priority: "High" },
  { id: "CH09", group: "Channel",         desc: "Neck slot width outer (Detail K)",  nominal: 4.85,  tol_lo: 0.00,  tol_hi: 0.02,  unit: "mm", method: "Edge-to-edge", sheet: 5, priority: "High" },

  // ── CIRCULAR HOLES (Sheet 2) — Ø0.50 THRU, loc tol ±0.02 ──
  { id: "HL01", group: "Holes",           desc: "Hole diameter (all)",      nominal: 0.50,  tol_lo: 0.00,  tol_hi: 0.00,  unit: "mm", method: "Circle fit (HoughCircles)", sheet: 2, priority: "Critical" },
  { id: "HL02", group: "Holes",           desc: "Hole location tolerance",  nominal: 0.00,  tol_lo: -0.02, tol_hi: 0.02,  unit: "mm", method: "Centroid vs nominal XY", sheet: 2, priority: "Critical" },
  { id: "HL03", group: "Holes",           desc: "Hole 1 X-location",        nominal: 20.65, tol_lo: -0.02, tol_hi: 0.02,  unit: "mm", method: "Centroid X", sheet: 2, priority: "High" },
  { id: "HL04", group: "Holes",           desc: "Hole 1 Y-location",        nominal: 8.15,  tol_lo: -0.02, tol_hi: 0.02,  unit: "mm", method: "Centroid Y", sheet: 2, priority: "High" },
  { id: "HL05", group: "Holes",           desc: "Hole 3 X-location",        nominal: 21.00, tol_lo: -0.02, tol_hi: 0.02,  unit: "mm", method: "Centroid X", sheet: 2, priority: "High" },
  { id: "HL06", group: "Holes",           desc: "Hole 3 Y-location",        nominal: 38.00, tol_lo: -0.02, tol_hi: 0.02,  unit: "mm", method: "Centroid Y", sheet: 2, priority: "High" },
  { id: "HL07", group: "Holes",           desc: "Hole 4 Y-location",        nominal: 48.00, tol_lo: -0.02, tol_hi: 0.02,  unit: "mm", method: "Centroid Y", sheet: 2, priority: "High" },
  { id: "HL08", group: "Holes",           desc: "Hole 10 X-location",       nominal: 35.27, tol_lo: -0.02, tol_hi: 0.02,  unit: "mm", method: "Centroid X", sheet: 2, priority: "High" },
  { id: "HL09", group: "Holes",           desc: "Hole 13 Y-location",       nominal: 70.50, tol_lo: -0.02, tol_hi: 0.02,  unit: "mm", method: "Centroid Y", sheet: 2, priority: "High" },

  // ── MICRO-FEATURES / SECTION D-D (Sheet 3) — step heights excluded (not measurable by top-down microscope) ──
  { id: "MF03", group: "Micro Features",  desc: "Micro channel width",      nominal: 0.30,  tol_lo: 0.00,  tol_hi: 0.02,  unit: "mm", method: "Min wall distance", sheet: 3, priority: "Critical" },
  { id: "MF04", group: "Micro Features",  desc: "Filter ridge width (typ)", nominal: 0.50,  tol_lo: -0.05, tol_hi: 0.00,  unit: "mm", method: "Edge measurement", sheet: 3, priority: "High" },
  { id: "MF05", group: "Micro Features",  desc: "Filter pillar width (typ)",nominal: 0.30,  tol_lo: 0.00,  tol_hi: 0.05,  unit: "mm", method: "Edge measurement", sheet: 3, priority: "High" },

  // ── FLUID CHAMBER (Sheet 4) ──
  { id: "FC01", group: "Fluid Chamber",   desc: "Chamber overall length",   nominal: 40.00, tol_lo: 0.00,  tol_hi: 0.05,  unit: "mm", method: "Edge-to-edge", sheet: 4, priority: "High" },
  { id: "FC02", group: "Fluid Chamber",   desc: "Chamber overall width",    nominal: 32.50, tol_lo: 0.00,  tol_hi: 0.05,  unit: "mm", method: "Edge-to-edge", sheet: 4, priority: "High" },
  { id: "FC03", group: "Fluid Chamber",   desc: "Inner channel length",     nominal: 13.00, tol_lo: 0.00,  tol_hi: 0.05,  unit: "mm", method: "Edge-to-edge", sheet: 4, priority: "High" },
  { id: "FC04", group: "Fluid Chamber",   desc: "Port diameter",            nominal: 5.00,  tol_lo: -0.05, tol_hi: 0.00,  unit: "mm", method: "Circle fit", sheet: 4, priority: "Critical" },
  { id: "FC05", group: "Fluid Chamber",   desc: "Port location X",          nominal: 35.60, tol_lo: -0.05, tol_hi: 0.05,  unit: "mm", method: "Centroid X", sheet: 4, priority: "High" },
  { id: "FC06", group: "Fluid Chamber",   desc: "Chamber wall thickness",   nominal: 1.65,  tol_lo: 0.00,  tol_hi: 0.02,  unit: "mm", method: "Wall thickness", sheet: 4, priority: "High" },
  { id: "FC07", group: "Fluid Chamber",   desc: "Inlet taper angle",        nominal: 7.50,  tol_lo: -0.05, tol_hi: 0.05,  unit: "°",  method: "Angular meas.", sheet: 4, priority: "Medium" },
  { id: "FC08", group: "Fluid Chamber",   desc: "Fillet radius (2xR1.20)",  nominal: 1.20,  tol_lo: -0.05, tol_hi: 0.05,  unit: "mm", method: "Circle fit", sheet: 4, priority: "Low" },
  { id: "FC09", group: "Fluid Chamber",   desc: "Fillet radius (2xR0.91)",  nominal: 0.91,  tol_lo: -0.05, tol_hi: 0.05,  unit: "mm", method: "Circle fit", sheet: 4, priority: "Low" },

  // ── CONNECTOR / LATCH (Sheet 5) ──
  { id: "CN01", group: "Connector",       desc: "Connector length",         nominal: 33.35, tol_lo: 0.00,  tol_hi: 0.05,  unit: "mm", method: "Edge-to-edge", sheet: 5, priority: "High" },
  { id: "CN02", group: "Connector",       desc: "Connector width",          nominal: 31.15, tol_lo: -0.02, tol_hi: 0.02,  unit: "mm", method: "Edge-to-edge", sheet: 5, priority: "High" },
  { id: "CN03", group: "Connector",       desc: "Latch slot width",         nominal: 4.70,  tol_lo: -0.02, tol_hi: 0.02,  unit: "mm", method: "Edge measurement", sheet: 5, priority: "High" },
  { id: "CN04", group: "Connector",       desc: "Latch slot height",        nominal: 4.59,  tol_lo: -0.02, tol_hi: 0.02,  unit: "mm", method: "Edge measurement", sheet: 5, priority: "High" },
  { id: "CN05", group: "Connector",       desc: "Fluid port width",         nominal: 5.00,  tol_lo: 0.00,  tol_hi: 0.05,  unit: "mm", method: "Edge measurement", sheet: 5, priority: "Critical" },
  { id: "CN07", group: "Connector",       desc: "Channel angle",            nominal: 30.00, tol_lo: 0.00,  tol_hi: 0.00,  unit: "°",  method: "Angular meas.", sheet: 5, priority: "Medium" },

  // ── REAR / SEAL FACE (Sheet 6) ──
  { id: "RF01", group: "Rear/Seal",       desc: "Rear face length",         nominal: 24.40, tol_lo: 0.00,  tol_hi: 0.05,  unit: "mm", method: "Edge-to-edge", sheet: 6, priority: "High" },
  { id: "RF02", group: "Rear/Seal",       desc: "Rear face width",          nominal: 22.00, tol_lo: -0.05, tol_hi: 0.00,  unit: "mm", method: "Edge-to-edge", sheet: 6, priority: "High" },
  { id: "RF03", group: "Rear/Seal",       desc: "Seal groove OD",           nominal: 24.40, tol_lo: 0.00,  tol_hi: 0.05,  unit: "mm", method: "Circle fit", sheet: 6, priority: "High" },
  { id: "RF04", group: "Rear/Seal",       desc: "Seal groove ID",           nominal: 22.00, tol_lo: -0.05, tol_hi: 0.00,  unit: "mm", method: "Circle fit", sheet: 6, priority: "High" },
  { id: "RF05", group: "Rear/Seal",       desc: "Seal groove radius",       nominal: 25.00, tol_lo: -0.05, tol_hi: 0.05,  unit: "mm", method: "Arc measurement", sheet: 6, priority: "Medium" },
  { id: "RF06", group: "Rear/Seal",       desc: "Vent slot width",          nominal: 0.50,  tol_lo: 0.00,  tol_hi: 0.05,  unit: "mm", method: "Gap measure", sheet: 6, priority: "High" },
  { id: "RF07", group: "Rear/Seal",       desc: "Vent slot angle",          nominal: 20.00, tol_lo: -0.05, tol_hi: 0.05,  unit: "°",  method: "Angular meas.", sheet: 6, priority: "Medium" },
  { id: "RF08", group: "Rear/Seal",       desc: "Micro groove width",       nominal: 0.625, tol_lo: -0.02, tol_hi: 0.02,  unit: "mm", method: "Edge measurement", sheet: 6, priority: "Critical" },
  { id: "RF11", group: "Rear/Seal",       desc: "Rear outer dimension",     nominal: 19.00, tol_lo: -0.05, tol_hi: 0.05,  unit: "mm", method: "Edge-to-edge", sheet: 6, priority: "Medium" },
];

// All unique groups
const GROUPS = [...new Set(FEATURES.map(f => f.group))];
const SHEETS = [1,2,3,4,5,6];
const PRIORITIES = ["Critical","High","Medium","Low"];
const PRIORITY_COLOR = { Critical: "#EF4444", High: "#F97316", Medium: "#F59E0B", Low: "#10B981" };
const PRIORITY_BG = { Critical: "rgba(239,68,68,0.15)", High: "rgba(249,115,22,0.15)", Medium: "rgba(245,158,11,0.15)", Low: "rgba(16,185,129,0.15)" };
const GROUP_COLOR = {
  "Overall Body": "#0EA5E9", "Channel": "#8B5CF6", "Holes": "#EC4899",
  "Micro Features": "#F59E0B", "Fluid Chamber": "#10B981", "Connector": "#F97316", "Rear/Seal": "#6366F1"
};


// Hole table from Sheet 2
const HOLES = [
  { tag: 1,  x: 20.65, y: 8.15 },
  { tag: 3,  x: 21.00, y: 38.00 },
  { tag: 4,  x: 21.00, y: 48.00 },
  { tag: 5,  x: 24.50, y: 48.94 },
  { tag: 6,  x: 27.06, y: 51.50 },
  { tag: 7,  x: 27.89, y: 56.22 },
  { tag: 8,  x: 21.00, y: 55.00 },
  { tag: 9,  x: 14.94, y: 51.50 },
  { tag: 10, x: 35.27, y: 53.70 },
  { tag: 12, x: 33.64, y: 62.48 },
  { tag: 13, x: 35.78, y: 70.50 },
  { tag: 14, x: 24.50, y: 40.44 },
];

export default function App() {
  const [tab, setTab] = useState("tolerances");
  const [groupFilter, setGroupFilter] = useState("All");
  const [priorityFilter, setPriorityFilter] = useState("All");
  const [sheetFilter, setSheetFilter] = useState("All");
  const [search, setSearch] = useState("");
  const [sortCol, setSortCol] = useState("id");
  const [sortAsc, setSortAsc] = useState(true);

  const filtered = FEATURES
    .filter(f => groupFilter === "All" || f.group === groupFilter)
    .filter(f => priorityFilter === "All" || f.priority === priorityFilter)
    .filter(f => sheetFilter === "All" || f.sheet === Number(sheetFilter))
    .filter(f => search === "" || f.id.toLowerCase().includes(search.toLowerCase()) || f.desc.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      let va = a[sortCol], vb = b[sortCol];
      if (typeof va === "string") return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
      return sortAsc ? va - vb : vb - va;
    });

  const handleSort = col => { if (sortCol === col) setSortAsc(!sortAsc); else { setSortCol(col); setSortAsc(true); } };
  const SortIcon = ({ col }) => sortCol === col ? (sortAsc ? " ▲" : " ▼") : " ⇅";

  const stats = {
    total: FEATURES.length,
    critical: FEATURES.filter(f => f.priority === "Critical").length,
    high: FEATURES.filter(f => f.priority === "High").length,
    sheets: 6,
    groups: GROUPS.length,
  };

  // Hole map SVG
  const HoleMap = () => {
    const W = 280, H = 460;
    const pad = 30;
    const scaleX = (x) => pad + (x / 40) * (W - 2*pad);
    const scaleY = (y) => H - pad - (y / 74) * (H - 2*pad);
    return (
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", maxWidth: "300px", background: "#0A1628", borderRadius: "10px", border: "1px solid #1E293B" }}>
        {/* Body outline */}
        <rect x={pad} y={pad} width={W-2*pad} height={H-2*pad} rx="12" ry="12"
          fill="none" stroke="#1E3A5F" strokeWidth="2"/>
        {/* Axes labels */}
        <text x={pad} y={H-8} fill="#334155" fontSize="9" textAnchor="middle">0</text>
        <text x={W-pad} y={H-8} fill="#334155" fontSize="9" textAnchor="middle">40</text>
        <text x={8} y={pad} fill="#334155" fontSize="9" textAnchor="middle">74</text>
        <text x={8} y={H-pad} fill="#334155" fontSize="9" textAnchor="middle">0</text>
        <text x={W/2} y={H-2} fill="#475569" fontSize="8" textAnchor="middle">X (mm)</text>
        {/* Y axis label */}
        <text x={3} y={H/2} fill="#475569" fontSize="8" textAnchor="middle"
          transform={`rotate(-90, 3, ${H/2})`}>Y (mm)</text>
        {/* Origin crosshair */}
        <line x1={pad-4} y1={H-pad} x2={pad+8} y2={H-pad} stroke="#334155" strokeWidth="1"/>
        <line x1={pad} y1={H-pad+4} x2={pad} y2={H-pad-8} stroke="#334155" strokeWidth="1"/>
        {/* Holes */}
        {HOLES.map(h => (
          <g key={h.tag}>
            <circle cx={scaleX(h.x)} cy={scaleY(h.y)} r={5}
              fill="rgba(236,72,153,0.25)" stroke="#EC4899" strokeWidth="1.5"/>
            <text x={scaleX(h.x)+7} y={scaleY(h.y)+4} fill="#94A3B8" fontSize="8">{h.tag}</text>
          </g>
        ))}
        <text x={W/2} y={20} fill="#64748B" fontSize="9" textAnchor="middle">Sheet 2 — Hole Location Map</text>
        <text x={W/2} y={30} fill="#475569" fontSize="8" textAnchor="middle">Ø0.50 THRU, Loc tol ±0.02mm</text>
      </svg>
    );
  };

  return (
    <div style={{ minHeight: "100vh", background: "#060B14", color: "#CBD5E1", fontFamily: "'Inter','Segoe UI',system-ui,sans-serif" }}>
      {/* Header */}
      <div style={{ background: "#0D1B2A", borderBottom: "1px solid #1E293B", padding: "1.25rem 1.5rem" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.75rem" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                <span style={{ fontSize: "1.4rem" }}>🔬</span>
                <h1 style={{ margin: 0, fontSize: "1.25rem", fontWeight: 800, color: "#F1F5F9" }}>Achira Beta Cartridge — QC Phase 1</h1>
              </div>
              <p style={{ margin: "0.2rem 0 0", color: "#475569", fontSize: "0.8rem" }}>
                DWG ACMCTA001 · PMMA · 6 Sheets · {stats.total} features · {stats.critical} critical · Depth features excluded (top-down microscope only)
              </p>
            </div>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              {PRIORITIES.map(p => (
                <span key={p} style={{ padding: "0.2rem 0.65rem", borderRadius: "999px", fontSize: "0.72rem", fontWeight: 700, background: PRIORITY_BG[p], color: PRIORITY_COLOR[p] }}>
                  {p}: {FEATURES.filter(f => f.priority === p).length}
                </span>
              ))}
            </div>
          </div>
          {/* Tabs */}
          <div style={{ display: "flex", gap: "0.25rem", marginTop: "1rem" }}>
            {[
              { id: "tolerances", label: "📐 Tolerance Table" },
              { id: "holes", label: "🎯 Hole Map" },

              { id: "summary", label: "📊 Summary" },
            ].map(t => (
              <button key={t.id} onClick={() => setTab(t.id)} style={{
                padding: "0.45rem 0.9rem", borderRadius: "8px", border: "none",
                background: tab === t.id ? "#1E293B" : "transparent",
                color: tab === t.id ? "#E2E8F0" : "#64748B",
                cursor: "pointer", fontSize: "0.82rem", fontWeight: tab === t.id ? 600 : 400,
              }}>{t.label}</button>
            ))}
          </div>
        </div>
      </div>

      <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "1.5rem" }}>

        {/* ── TOLERANCE TABLE ── */}
        {tab === "tolerances" && (
          <div>
            {/* Filters */}
            <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", marginBottom: "1.25rem", alignItems: "center" }}>
              <input value={search} onChange={e => setSearch(e.target.value)}
                placeholder="Search ID or description…"
                style={{ flex: "1 1 180px", minWidth: "140px", background: "#0D1B2A", border: "1px solid #1E293B", color: "#E2E8F0", borderRadius: "8px", padding: "0.5rem 0.75rem", fontSize: "0.82rem" }} />
              {[
                { label: "Group", val: groupFilter, set: setGroupFilter, opts: ["All", ...GROUPS] },
                { label: "Priority", val: priorityFilter, set: setPriorityFilter, opts: ["All", ...PRIORITIES] },
                { label: "Sheet", val: sheetFilter, set: setSheetFilter, opts: ["All", ...SHEETS] },
              ].map(({ label, val, set, opts }) => (
                <select key={label} value={val} onChange={e => set(e.target.value)}
                  style={{ background: "#0D1B2A", border: "1px solid #1E293B", color: "#E2E8F0", borderRadius: "8px", padding: "0.5rem 0.65rem", fontSize: "0.82rem" }}>
                  {opts.map(o => <option key={o} value={o}>{label}: {o}</option>)}
                </select>
              ))}
              <span style={{ color: "#475569", fontSize: "0.8rem" }}>{filtered.length} features</span>
            </div>

            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
                <thead>
                  <tr style={{ background: "#0D1B2A", borderBottom: "1px solid #1E293B" }}>
                    {[
                      { col: "id", label: "ID" },
                      { col: "group", label: "Group" },
                      { col: "desc", label: "Description" },
                      { col: "nominal", label: "Nominal" },
                      { col: "tol_lo", label: "Tol −" },
                      { col: "tol_hi", label: "Tol +" },
                      { col: "unit", label: "Unit" },
                      { col: "method", label: "CV Method" },
                      { col: "sheet", label: "Sheet" },
                      { col: "priority", label: "Priority" },
                    ].map(h => (
                      <th key={h.col} onClick={() => handleSort(h.col)}
                        style={{ padding: "0.65rem 0.75rem", textAlign: "left", color: "#64748B", fontWeight: 700, cursor: "pointer", whiteSpace: "nowrap", userSelect: "none" }}>
                        {h.label}<SortIcon col={h.col} />
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((f, i) => (
                    <tr key={f.id} style={{ borderBottom: "1px solid #0F172A", background: i % 2 === 0 ? "transparent" : "#080E1A" }}>
                      <td style={{ padding: "0.6rem 0.75rem", fontFamily: "monospace", color: "#0EA5E9", fontWeight: 700 }}>{f.id}</td>
                      <td style={{ padding: "0.6rem 0.75rem" }}>
                        <span style={{ padding: "0.15rem 0.5rem", borderRadius: "6px", fontSize: "0.72rem", fontWeight: 600, background: `${GROUP_COLOR[f.group]}22`, color: GROUP_COLOR[f.group] }}>{f.group}</span>
                      </td>
                      <td style={{ padding: "0.6rem 0.75rem", color: "#CBD5E1" }}>{f.desc}</td>
                      <td style={{ padding: "0.6rem 0.75rem", color: "#F59E0B", fontWeight: 700, fontFamily: "monospace" }}>{f.nominal.toFixed(f.nominal < 10 ? 3 : 2)}</td>
                      <td style={{ padding: "0.6rem 0.75rem", color: "#F87171", fontFamily: "monospace" }}>{f.tol_lo > 0 ? "+" : ""}{f.tol_lo.toFixed(2)}</td>
                      <td style={{ padding: "0.6rem 0.75rem", color: "#34D399", fontFamily: "monospace" }}>+{f.tol_hi.toFixed(2)}</td>
                      <td style={{ padding: "0.6rem 0.75rem", color: "#64748B" }}>{f.unit}</td>
                      <td style={{ padding: "0.6rem 0.75rem", color: "#94A3B8", fontSize: "0.78rem" }}>{f.method}</td>
                      <td style={{ padding: "0.6rem 0.75rem", color: "#475569", textAlign: "center" }}>{f.sheet}</td>
                      <td style={{ padding: "0.6rem 0.75rem" }}>
                        <span style={{ padding: "0.2rem 0.55rem", borderRadius: "999px", fontSize: "0.72rem", fontWeight: 700, background: PRIORITY_BG[f.priority], color: PRIORITY_COLOR[f.priority] }}>
                          {f.priority}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── HOLE MAP ── */}
        {tab === "holes" && (
          <div style={{ display: "flex", gap: "2rem", flexWrap: "wrap" }}>
            <HoleMap />
            <div style={{ flex: 1, minWidth: "280px" }}>
              <h3 style={{ color: "#E2E8F0", fontSize: "1rem", margin: "0 0 1rem" }}>Sheet 2 — Hole Location Table</h3>
              <div style={{ fontSize: "0.78rem", color: "#475569", marginBottom: "0.75rem" }}>
                All holes: Ø0.50 THRU · Location tolerance: ±0.02 mm · Note: DEBURR ALL HOLES
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
                <thead>
                  <tr style={{ background: "#0D1B2A" }}>
                    {["TAG", "X (mm)", "Y (mm)", "Ø (mm)", "Loc Tol"].map(h => (
                      <th key={h} style={{ padding: "0.55rem 0.75rem", textAlign: "left", color: "#64748B", fontWeight: 700 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {HOLES.map((h, i) => (
                    <tr key={h.tag} style={{ borderTop: "1px solid #1E293B", background: i % 2 ? "#080E1A" : "transparent" }}>
                      <td style={{ padding: "0.55rem 0.75rem", color: "#EC4899", fontWeight: 700, fontFamily: "monospace" }}>{h.tag}</td>
                      <td style={{ padding: "0.55rem 0.75rem", fontFamily: "monospace", color: "#CBD5E1" }}>{h.x.toFixed(2)}</td>
                      <td style={{ padding: "0.55rem 0.75rem", fontFamily: "monospace", color: "#CBD5E1" }}>{h.y.toFixed(2)}</td>
                      <td style={{ padding: "0.55rem 0.75rem", fontFamily: "monospace", color: "#F59E0B" }}>0.50</td>
                      <td style={{ padding: "0.55rem 0.75rem", color: "#34D399" }}>±0.02</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ marginTop: "1rem", padding: "0.9rem", background: "#0D1B2A", border: "1px solid #1E293B", borderRadius: "10px", fontSize: "0.82rem", color: "#64748B" }}>
                <strong style={{ color: "#94A3B8" }}>CV Approach for Holes:</strong><br/>
                Detect with <code style={{ color: "#0EA5E9" }}>cv2.HoughCircles</code>, then verify centroid XY against this table. Flag any hole where centroid deviation &gt; 0.02 mm or diameter outside 0.50 ± tolerance.
              </div>
            </div>
          </div>
        )}

        {/* ── SUMMARY ── */}
        {tab === "summary" && (
          <div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(160px,1fr))", gap: "1rem", marginBottom: "1.5rem" }}>
              {[
                { label: "Total Features", val: stats.total, color: "#0EA5E9" },
                { label: "Critical", val: stats.critical, color: "#EF4444" },
                { label: "High Priority", val: stats.high, color: "#F97316" },
                { label: "Drawing Sheets", val: stats.sheets, color: "#8B5CF6" },
                { label: "Feature Groups", val: stats.groups, color: "#10B981" },
                { label: "Holes to Track", val: 12, color: "#EC4899" },
              ].map(s => (
                <div key={s.label} style={{ background: "#0D1B2A", border: `1px solid ${s.color}33`, borderRadius: "10px", padding: "1rem", textAlign: "center" }}>
                  <div style={{ fontSize: "1.8rem", fontWeight: 800, color: s.color }}>{s.val}</div>
                  <div style={{ fontSize: "0.8rem", color: "#64748B", marginTop: "0.25rem" }}>{s.label}</div>
                </div>
              ))}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              <div style={{ background: "#0D1B2A", border: "1px solid #1E293B", borderRadius: "10px", padding: "1.25rem" }}>
                <h4 style={{ margin: "0 0 0.75rem", color: "#94A3B8", fontSize: "0.85rem", fontWeight: 700, textTransform: "uppercase" }}>Features by Group</h4>
                {GROUPS.map(g => {
                  const count = FEATURES.filter(f => f.group === g).length;
                  return (
                    <div key={g} style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
                      <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: GROUP_COLOR[g], flexShrink: 0 }} />
                      <span style={{ fontSize: "0.82rem", color: "#94A3B8", flex: 1 }}>{g}</span>
                      <span style={{ fontSize: "0.82rem", color: GROUP_COLOR[g], fontWeight: 700 }}>{count}</span>
                      <div style={{ width: "80px", background: "#1E293B", borderRadius: "999px", height: "5px" }}>
                        <div style={{ width: `${(count / stats.total) * 100}%`, background: GROUP_COLOR[g], borderRadius: "999px", height: "5px" }} />
                      </div>
                    </div>
                  );
                })}
              </div>

              <div style={{ background: "#0D1B2A", border: "1px solid #1E293B", borderRadius: "10px", padding: "1.25rem" }}>
                <h4 style={{ margin: "0 0 0.75rem", color: "#94A3B8", fontSize: "0.85rem", fontWeight: 700, textTransform: "uppercase" }}>Tightest Tolerances</h4>
                {FEATURES
                  .filter(f => f.unit === "mm")
                  .sort((a, b) => (Math.abs(a.tol_lo) + a.tol_hi) - (Math.abs(b.tol_lo) + b.tol_hi))
                  .slice(0, 8)
                  .map(f => (
                    <div key={f.id} style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.4rem" }}>
                      <span style={{ fontFamily: "monospace", color: "#0EA5E9", fontSize: "0.72rem", minWidth: "40px" }}>{f.id}</span>
                      <span style={{ fontSize: "0.78rem", color: "#64748B", flex: 1 }}>{f.desc}</span>
                      <span style={{ fontFamily: "monospace", fontSize: "0.78rem", color: PRIORITY_COLOR[f.priority] }}>
                        {f.tol_lo}/{f.tol_hi > 0 ? "+" : ""}{f.tol_hi} mm
                      </span>
                    </div>
                  ))}
              </div>
            </div>

            <div style={{ marginTop: "1rem", background: "#0D1B2A", border: "1px solid #EF444433", borderRadius: "10px", padding: "1.25rem" }}>
              <h4 style={{ margin: "0 0 0.75rem", color: "#EF4444", fontSize: "0.85rem", fontWeight: 700 }}>⚠ Critical Features — Must Pass for Release</h4>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(220px,1fr))", gap: "0.5rem" }}>
                {FEATURES.filter(f => f.priority === "Critical").map(f => (
                  <div key={f.id} style={{ padding: "0.6rem 0.85rem", background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)", borderRadius: "8px", fontSize: "0.8rem" }}>
                    <span style={{ fontFamily: "monospace", color: "#EF4444", fontWeight: 700 }}>{f.id}</span>
                    <span style={{ color: "#CBD5E1", marginLeft: "0.5rem" }}>{f.desc}</span>
                    <div style={{ color: "#64748B", fontSize: "0.72rem", marginTop: "0.2rem" }}>
                      {f.nominal} {f.unit} [{f.tol_lo}/+{f.tol_hi}]
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
