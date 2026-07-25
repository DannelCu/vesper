import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'
import { fileURLToPath } from 'url'

const __dirname = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      // Two HTML entry points: the SPA shell, and the detached process-detail
      // window (docs/multiwindow.md). Vite's dev server already serves both
      // from disk without this — it only matters for `vite build`/`vesper
      // build`, so the packaged app's dist/ actually contains both files.
      input: {
        main: resolve(__dirname, 'index.html'),
        'process-detail': resolve(__dirname, 'process-detail.html'),
      },
    },
  },
})
