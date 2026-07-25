// A hand-drawn SVG sliding-window line chart — no charting library, per the
// plan. Takes a series of { ts, value } points and draws them normalized to
// 0-100 (both cpu% and mem% are already percentages).
export default function Chart({ series, color, label, height = 120 }) {
  const width = 100 // viewBox units — scales to the container via CSS
  const points = series.slice(-120)

  const path =
    points.length > 1
      ? points
          .map((p, i) => {
            const x = (i / (points.length - 1)) * width
            const y = height - (p.value / 100) * height
            return `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`
          })
          .join(' ')
      : ''

  const latest = points.length ? points[points.length - 1].value : 0

  return (
    <div className="chart">
      <div className="chart-header">
        <span className="chart-label">{label}</span>
        <span className="chart-value">{latest.toFixed(0)}%</span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="chart-svg">
        {[25, 50, 75].map((line) => (
          <line
            key={line}
            x1="0"
            x2={width}
            y1={height - (line / 100) * height}
            y2={height - (line / 100) * height}
            className="chart-gridline"
          />
        ))}
        {path && <path d={path} fill="none" stroke={color} strokeWidth="1.5" />}
      </svg>
    </div>
  )
}
