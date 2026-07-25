// docs/recipes/theming.md, applied: system dark/light via vesper-theme when
// installed, a fixed light theme otherwise (the plan's degrade contract —
// no manual toggle, since without the plugin there is nothing to react to
// and CSS alone already gives every window the OS preference at load time).
export function applyTheme(isDark) {
  document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light')
}

export async function initTheme(hasThemePlugin) {
  if (!hasThemePlugin) return

  const { is_dark } = await window.vesper.theme.get()
  applyTheme(is_dark)
  window.vesper.theme.onChange(({ is_dark: dark }) => applyTheme(dark))
}
