// Native right-click menus do not exist in a WebView Vesper can drive —
// see docs/recipes/context-menus.md and KNOWN-ISSUES.md KI2. Right-clicking
// still hits the engine's default menu unless the page disables it, which
// is exactly what `vesper.security.lockdown()` does in main.jsx — that
// call is *why* this component has to exist at all: with the browser menu
// gone, this is the only one left. Positioned in-viewport, closes on an
// outside click or Escape, and supports arrow-key navigation.
import { useEffect, useRef } from 'react'

export default function ContextMenu({ x, y, items, onClose }) {
  const ref = useRef(null)

  useEffect(() => {
    function onDocClick(e) {
      if (ref.current && !ref.current.contains(e.target)) onClose()
    }
    function onKeyDown(e) {
      if (e.key === 'Escape') {
        onClose()
        return
      }
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault()
        const focusable = ref.current.querySelectorAll('button:not(:disabled)')
        const list = Array.from(focusable)
        const idx = list.indexOf(document.activeElement)
        const next =
          e.key === 'ArrowDown'
            ? list[(idx + 1) % list.length]
            : list[(idx - 1 + list.length) % list.length]
        next?.focus()
      }
    }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [onClose])

  // Keep the menu inside the viewport rather than letting it spill off the
  // right/bottom edge — a menu you cannot see is a menu you cannot use.
  const style = {
    left: Math.min(x, window.innerWidth - 220),
    top: Math.min(y, window.innerHeight - items.length * 32 - 16),
  }

  useEffect(() => {
    ref.current?.querySelector('button:not(:disabled)')?.focus()
  }, [])

  return (
    <div className="context-menu" style={style} ref={ref} role="menu">
      {items.map((item, i) =>
        item.separator ? (
          <div className="context-separator" key={`sep-${i}`} />
        ) : (
          <button
            key={item.label}
            role="menuitem"
            className={item.danger ? 'context-item context-item--danger' : 'context-item'}
            disabled={item.disabled}
            title={item.disabledReason}
            onClick={() => {
              onClose()
              item.onSelect()
            }}
          >
            {item.label}
          </button>
        )
      )}
    </div>
  )
}
