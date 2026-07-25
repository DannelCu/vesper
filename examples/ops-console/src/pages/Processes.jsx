// The process table — sorting, filtering and pagination over a real psutil
// listing (docs/recipes/context-menus.md for the right-click menu). The
// "Terminate process" guard demo is deliberately left *enabled* for a
// viewer: clicking it as viewer is the point, not disabling it — see the
// README's guided tour.
import { useCallback, useEffect, useState } from 'react'
import { call, classifyError } from '../lib/vesperClient'
import ContextMenu from '../components/ContextMenu'
import Banner from '../components/Banner'

const PAGE_SIZE = 15

const COLUMNS = [
  ['pid', 'PID'],
  ['name', 'Name'],
  ['username', 'User'],
  ['cpu_percent', 'CPU %'],
  ['memory_percent', 'Mem %'],
  ['status', 'Status'],
]

export default function Processes() {
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [available, setAvailable] = useState(true)
  const [search, setSearch] = useState('')
  const [sortBy, setSortBy] = useState('cpu_percent')
  const [sortDir, setSortDir] = useState('desc')
  const [page, setPage] = useState(1)
  const [menu, setMenu] = useState(null)
  const [toast, setToast] = useState(null)

  const load = useCallback(async () => {
    const result = await call('processes.list', {
      search,
      sort_by: sortBy,
      sort_dir: sortDir,
      page,
      page_size: PAGE_SIZE,
    })
    setAvailable(result.available)
    setRows(result.items)
    setTotal(result.total)
  }, [search, sortBy, sortDir, page])

  useEffect(() => {
    load()
    const id = setInterval(load, 3000)
    return () => clearInterval(id)
  }, [load])

  function toggleSort(col) {
    if (sortBy === col) {
      setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'))
    } else {
      setSortBy(col)
      setSortDir('desc')
    }
  }

  function openMenu(e, row) {
    e.preventDefault()
    setMenu({ x: e.clientX, y: e.clientY, row })
  }

  async function terminate(row) {
    try {
      await call('processes.terminate', { pid: row.pid })
      setToast({ kind: 'ok', text: `Terminated ${row.name} (PID ${row.pid}).` })
      load()
    } catch (err) {
      const { phase, label, message } = classifyError(err)
      setToast({ kind: phase, text: `${label}: ${message}` })
    }
  }

  async function openDetail(row) {
    try {
      await call('processes:open_detail', { pid: row.pid })
    } catch (err) {
      const { label, message } = classifyError(err)
      setToast({ kind: 'command', text: `${label}: ${message}` })
    }
  }

  function copyPid(row) {
    window.vesper.clipboard.write(String(row.pid))
    setToast({ kind: 'ok', text: `Copied PID ${row.pid}.` })
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const bannerKind = (kind) =>
    kind === 'ok' ? 'info' : kind === 'policy' ? 'policy' : 'error'

  return (
    <div className="page">
      <h1>Processes</h1>

      {!available && (
        <Banner kind="warning">
          psutil is not installed — the process table is unavailable. Install
          it with <code>pip install psutil</code> to enable listing and
          terminating processes.
        </Banner>
      )}

      {toast && <Banner kind={bannerKind(toast.kind)}>{toast.text}</Banner>}

      <div className="toolbar">
        <input
          placeholder="Filter by name…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
        />
      </div>

      <table className="data-table">
        <thead>
          <tr>
            {COLUMNS.map(([key, label]) => (
              <th key={key} onClick={() => toggleSort(key)} className="sortable">
                {label}
                {sortBy === key ? (sortDir === 'desc' ? ' ↓' : ' ↑') : ''}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.pid} onContextMenu={(e) => openMenu(e, row)}>
              <td>{row.pid}</td>
              <td>{row.name}</td>
              <td>{row.username}</td>
              <td>{row.cpu_percent.toFixed(1)}</td>
              <td>{row.memory_percent.toFixed(1)}</td>
              <td>{row.status}</td>
            </tr>
          ))}
          {available && rows.length === 0 && (
            <tr>
              <td colSpan={COLUMNS.length} className="empty">
                No processes match.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      <div className="pagination">
        <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
          Prev
        </button>
        <span>
          Page {page} / {totalPages}
        </span>
        <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
          Next
        </button>
      </div>

      {menu && (
        <ContextMenu
          x={menu.x}
          y={menu.y}
          onClose={() => setMenu(null)}
          items={[
            { label: 'View detail in new window', onSelect: () => openDetail(menu.row) },
            { label: 'Copy PID', onSelect: () => copyPid(menu.row) },
            { separator: true },
            { label: 'Terminate process', danger: true, onSelect: () => terminate(menu.row) },
          ]}
        />
      )}
    </div>
  )
}
