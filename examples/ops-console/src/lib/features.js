// Merges this app's own optional pieces (system:features) with the
// framework's own optional backends (vesper.capabilities()) — the same
// two-source pattern launcher and media-vault use, see their `*:features`
// commands and README "Vesper features on show" tables.
export async function loadFeatures() {
  const [appFeatures, capabilities] = await Promise.all([
    window.vesper.invoke('system:features', {}),
    window.vesper.capabilities(),
  ])
  return { ...appFeatures, capabilities }
}
