// docs/recipes/real-time.md, applied: app.py's MetricsService samples on a
// background thread from the moment the app starts (independent of this
// page being open, so alerts keep working while you are on another
// screen) and emits "metrics:tick" — this page just listens and redraws.
import { useEffect, useState } from 'react'
import { call } from '../lib/vesperClient'
import Chart from '../components/Chart'
import Banner from '../components/Banner'

export default function Dashboard() {
  const [series, setSeries] = useState({ cpu: [], mem: [] })
  const [source, setSource] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function init() {
      const [history, src] = await Promise.all([
        call('metrics.history', { limit: 120 }),
        call('metrics.source'),
      ])
      if (cancelled) return
      setSource(src.source)
      setSeries({
        cpu: history.map((s) => ({ ts: s.ts, value: s.cpu })),
        mem: history.map((s) => ({ ts: s.ts, value: s.mem })),
      })
    }
    init()

    const unsub = window.vesper.on('metrics:tick', (sample) => {
      setSeries((prev) => ({
        cpu: [...prev.cpu.slice(-119), { ts: sample.ts, value: sample.cpu }],
        mem: [...prev.mem.slice(-119), { ts: sample.ts, value: sample.mem }],
      }))
      setSource(sample.synthetic ? 'synthetic' : 'sysinfo')
    })

    return () => {
      cancelled = true
      unsub()
    }
  }, [])

  return (
    <div className="page">
      <h1>Dashboard</h1>

      {source === 'synthetic' && (
        <Banner kind="warning">
          Showing synthetic data — install vesper-sysinfo for real CPU and
          memory readings.
        </Banner>
      )}

      <div className="chart-grid">
        <Chart series={series.cpu} color="#3b82f6" label="CPU" />
        <Chart series={series.mem} color="#a855f7" label="Memory" />
      </div>
    </div>
  )
}
