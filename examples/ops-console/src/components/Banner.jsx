export default function Banner({ kind = 'info', children }) {
  return <div className={`banner banner--${kind}`}>{children}</div>
}
