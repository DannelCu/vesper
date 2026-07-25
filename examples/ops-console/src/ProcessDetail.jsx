// The detached process-detail window — docs/recipes/state-between-windows.md.
// A separate document with its own JS context: the selection arrives over
// the event bus, and `processes:now_viewing` covers the race where this
// window finishes loading just after the event was already emitted (the
// same pattern media-vault's player.html uses for vault:now_playing).
import { useEffect, useState } from 'react'

export default function ProcessDetail() {
  const [detail, setDetail] = useState(null)

  useEffect(() => {
    const unsub = window.vesper.on('process:detail', setDetail)
    window.vesper.invoke('processes:now_viewing', {}).then((d) => {
      if (d) setDetail(d)
    })
    return unsub
  }, [])

  if (!detail) {
    return <div className="detail-window">Waiting for a process…</div>
  }

  const rows = [
    ['PID', detail.pid],
    ['Name', detail.name],
    ['Executable', detail.exe || '—'],
    ['Command line', (detail.cmdline || []).join(' ') || '—'],
    ['Status', detail.status],
    ['User', detail.username || '—'],
    ['CPU %', detail.cpu_percent.toFixed(1)],
    ['Memory %', detail.memory_percent.toFixed(1)],
    ['Threads', detail.num_threads],
    ['Started', detail.create_time ? new Date(detail.create_time * 1000).toLocaleString() : '—'],
  ]

  return (
    <div className="detail-window">
      <h1>{detail.name}</h1>
      <table className="data-table">
        <tbody>
          {rows.map(([label, value]) => (
            <tr key={label}>
              <td>{label}</td>
              <td>{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
