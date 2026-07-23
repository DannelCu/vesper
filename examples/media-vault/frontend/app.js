/*
 * Media Vault frontend.
 *
 * Two ideas worth reading for:
 *
 *   1. Capability-driven UI. Nothing here assumes ffmpeg, ffprobe or any plugin
 *      exists. What is missing is turned off with a reason, never left as a
 *      button that does nothing. See applyCapabilities().
 *
 *   2. The video element loads from the library's loopback server, not from
 *      file://, which is what makes the seek bar work.
 */

const $ = (id) => document.getElementById(id);

const state = {
  root: null,
  items: [],
  features: {},      // ffprobe / ffmpeg / watch, from the app
  caps: {},          // vesper.capabilities(), the framework's own backends
  playing: null,
  playingUrl: null,  // effective source (transcoded copy when needed)
  converting: null,  // path currently being transcoded, for progress routing
};

function setStatus(text, isError = false) {
  const el = $("status");
  el.textContent = text;
  el.classList.toggle("error", isError);
}

function formatSize(bytes) {
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes, unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit++; }
  return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function formatDuration(seconds) {
  if (!seconds) return null;
  const total = Math.round(seconds);
  const m = Math.floor(total / 60), s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

// ── Capabilities ────────────────────────────────────────────────────────────
//
// Runs once at startup. Every degradation the README documents is decided here.

async function applyCapabilities() {
  state.caps = await vesper.capabilities();
  state.features = await vesper.invoke("vault:features");

  const notices = [];

  if (!state.features.ffprobe && !state.features.ffmpeg) {
    notices.push({
      text: "ffmpeg not found — no thumbnails and no durations. Files still play.",
      fix: "Install ffmpeg (apt install ffmpeg / brew install ffmpeg)",
    });
  } else if (!state.features.ffmpeg) {
    notices.push({ text: "ffmpeg not found — no thumbnails.", fix: "Install ffmpeg" });
  } else if (!state.features.ffprobe) {
    notices.push({ text: "ffprobe not found — no durations or resolutions.", fix: "Install ffmpeg" });
  }

  if (!state.features.watch) {
    notices.push({
      text: "vesper-watch not installed — the library does not refresh by itself.",
      fix: "pip install -e ../../plugins/vesper-watch  (or press Refresh)",
    });
  }

  if (!state.caps.clipboard_files) {
    notices.push({
      text: "Copying files to the clipboard is unavailable on this system.",
      fix: "Linux: install xclip",
    });
  }

  const box = $("notices");
  box.hidden = notices.length === 0;
  box.innerHTML = notices
    .map((n) => `<div class="notice"><span>${n.text}</span><code>${n.fix}</code></div>`)
    .join("");
}

// ── Library ─────────────────────────────────────────────────────────────────

async function openFolder() {
  const picked = await vesper.dialog.pickFolder();
  if (!picked || !picked.length) return;
  await openLibrary(picked[0]);
}

async function openLibrary(path) {
  setStatus("Indexing…");
  try {
    const result = await vesper.invoke("vault:open_library", { path });
    state.root = result.root;
    state.items = result.items;
    $("library-path").textContent = result.root;
    $("refresh").disabled = false;
    $("make-sample").disabled = false;
    render();
    setStatus(`Indexed ${result.items.length} file(s).`);
  } catch (error) {
    setStatus(`Could not open library: ${error.message}`, true);
  }
}

async function refresh() {
  if (!state.root) return;
  state.items = await vesper.invoke("vault:index");
  render();
  setStatus(`Indexed ${state.items.length} file(s).`);
}

// ── Rendering ───────────────────────────────────────────────────────────────

// A video's play control depends on whether the browser can open its format.
// Web-native formats play directly; the rest need transcoding, which the app
// does with ffmpeg — so the button is "Convert & Play" when ffmpeg is present
// and a disabled, explained Play when it is not. Nothing is offered that would
// do nothing.
function playButton(item, index) {
  if (item.web_playable) {
    return `<button data-act="play" data-i="${index}">Play</button>`;
  }
  const ext = item.name.split(".").pop().toUpperCase();
  if (state.features.ffmpeg) {
    return `<button data-act="convert" data-i="${index}"
                    title="${ext} needs converting to play in a browser">Convert &amp; Play</button>`;
  }
  return `<button disabled
                  title="The browser can't play ${ext}; install ffmpeg to convert it">Play</button>`;
}

function render() {
  const grid = $("grid");
  $("empty").hidden = state.items.length > 0 || state.root !== null;
  grid.hidden = state.items.length === 0;

  grid.innerHTML = state.items.map((item, index) => {
    const meta = [];
    if (item.duration) meta.push(formatDuration(item.duration));
    if (item.width && item.height) meta.push(`${item.width}×${item.height}`);
    meta.push(formatSize(item.size));

    return `
      <article class="tile" data-index="${index}">
        <div class="thumb" data-thumb="${index}">
          ${item.kind === "image"
            ? `<img src="${item.url}" alt="" />`
            : `<span class="placeholder">▶</span>`}
        </div>
        <div class="tile-body">
          <div class="tile-name" title="${item.name}">${item.name}</div>
          <div class="tile-meta">${meta.join(" · ")}</div>
        </div>
        <div class="tile-actions">
          ${item.kind === "video" ? playButton(item, index) : ""}
          <button data-act="duplicate" data-i="${index}">Duplicate</button>
          <button data-act="rename" data-i="${index}">Rename</button>
          <button data-act="clipboard" data-i="${index}"
                  ${state.caps.clipboard_files ? "" : "disabled title='Needs xclip on Linux'"}>Copy</button>
          <button data-act="trash" data-i="${index}" class="danger">Trash</button>
        </div>
      </article>`;
  }).join("");

  loadThumbnails();
}

// Thumbnails are fetched one at a time after the grid is on screen: each one is
// an ffmpeg process, and firing thirty at once would freeze the machine for a
// cosmetic detail.
async function loadThumbnails() {
  if (!state.features.ffmpeg) return;

  for (const [index, item] of state.items.entries()) {
    if (item.kind !== "video") continue;
    try {
      const url = await vesper.invoke("vault:thumbnail", { path: item.path });
      if (!url) continue;
      const slot = document.querySelector(`[data-thumb="${index}"]`);
      if (slot) slot.innerHTML = `<img src="${url}" alt="" />`;
    } catch {
      // A file ffmpeg cannot read is not worth interrupting the grid for.
    }
  }
}

// ── Playback ────────────────────────────────────────────────────────────────

// srcUrl overrides item.url — used for a transcoded copy, whose URL points at
// the converted mp4 rather than the original the browser cannot open.
async function play(item, srcUrl = null) {
  state.playing = item;
  state.playingUrl = srcUrl || item.url;
  $("player-panel").hidden = false;
  $("player-name").textContent = item.name;
  $("player").src = state.playingUrl;
  $("player").play().catch(() => {});
  // Keep the machine awake only while something is actually playing.
  await vesper.invoke("vault:playback_started");
}

// Transcode a non-web format to mp4, then play the result. The conversion can
// take a while for a long film, so the button turns into a live progress
// indicator (fed by transcode:progress events) instead of looking frozen.
async function convertAndPlay(item, button) {
  state.converting = item.path;
  if (button) {
    button.disabled = true;
    button.dataset.label = button.textContent;
    button.textContent = "Converting… 0%";
  }
  setStatus(`Converting ${item.name} to a web-playable format… this can take a while.`);
  try {
    const url = await vesper.invoke("vault:transcode", { path: item.path });
    setStatus(`Playing ${item.name}`);
    return play(item, url);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    state.converting = null;
    if (button) {
      button.disabled = false;
      button.textContent = button.dataset.label || "Convert & Play";
    }
  }
}

// Progress for the running conversion, pushed from the Python side. Updates the
// button of the file being converted; ignored for any other.
vesper.on("transcode:progress", ({ path, percent }) => {
  if (path !== state.converting) return;
  const button = document.querySelector('[data-act="convert"]:disabled');
  if (button) button.textContent = `Converting… ${percent}%`;
});

async function stopPlayback() {
  $("player").pause();
  $("player").removeAttribute("src");
  $("player-panel").hidden = true;
  state.playing = null;
  state.playingUrl = null;
  await vesper.invoke("vault:playback_stopped");
}

// ── Item actions ────────────────────────────────────────────────────────────

async function handleAction(action, item, button) {
  try {
    if (action === "play") return play(item);
    if (action === "convert") return convertAndPlay(item, button);

    if (action === "duplicate") {
      await vesper.invoke("vault:duplicate", { path: item.path });
      setStatus(`Duplicated ${item.name}`);
      return refresh();
    }

    if (action === "rename") {
      // See docs/recipes/text-input.md for why this lives in the page.
      const name = await promptText(`New name for ${item.name}`, item.name);
      if (!name || name === item.name) return;
      await vesper.invoke("vault:rename", { path: item.path, new_name: name });
      setStatus(`Renamed to ${name}`);
      return refresh();
    }

    if (action === "clipboard") {
      const ok = await vesper.invoke("vault:copy_to_clipboard", { paths: [item.path] });
      setStatus(ok
        ? `${item.name} copied — paste it in your file manager.`
        : "The system clipboard refused the file.", !ok);
      return;
    }

    if (action === "trash") {
      // confirm(message, title) — message first.
      const confirmed = await vesper.dialog.confirm(
        `Move ${item.name} to the trash?`, "Move to trash");
      if (!confirmed) return;
      await vesper.invoke("vault:trash", { path: item.path });
      if (state.playing && state.playing.path === item.path) await stopPlayback();
      setStatus(`${item.name} moved to the trash.`);
      return refresh();
    }
  } catch (error) {
    // fs.trash raises when no trash backend exists — deleting is destructive, so
    // the framework refuses rather than pretending. Show it.
    setStatus(error.message, true);
  }
}

// Ask the user for a string. Resolves to the text, or null if cancelled.
// The pattern from docs/recipes/text-input.md — Enter and Escape come free from
// <form method="dialog">, so there are no key handlers here.
function promptText(message, initial = "") {
  const dialog = $("prompt");
  const input = $("prompt-input");

  $("prompt-label").textContent = message;
  input.value = initial;

  return new Promise((resolve) => {
    dialog.addEventListener("close", () => {
      resolve(dialog.returnValue === "ok" ? input.value.trim() : null);
    }, { once: true });

    dialog.showModal();
    input.select();
  });
}


// ── Wiring ──────────────────────────────────────────────────────────────────

$("open-folder").addEventListener("click", openFolder);
$("refresh").addEventListener("click", refresh);
$("close-player").addEventListener("click", stopPlayback);

$("detach").addEventListener("click", async () => {
  if (!state.playing) return;
  await vesper.invoke("vault:open_player", {
    // The effective URL — the transcoded copy when the original needed it.
    url: state.playingUrl, name: state.playing.name,
  });
  await stopPlayback();
});

$("grid").addEventListener("click", (event) => {
  const button = event.target.closest("[data-act]");
  if (!button) return;
  handleAction(button.dataset.act, state.items[Number(button.dataset.i)], button);
});

$("make-sample").addEventListener("click", async () => {
  $("progress").hidden = false;
  $("make-sample").disabled = true;
  try {
    await vesper.invoke("vault:generate_sample");
    setStatus("Sample clip downloaded.");
    await refresh();
  } catch (error) {
    setStatus(`Download failed: ${error.message}`, true);
  } finally {
    $("progress").hidden = true;
    $("make-sample").disabled = false;
  }
});

// Progress arrives as events while the Python side downloads, which is what
// lets the taskbar bar and this one stay in step.
vesper.on("sample:progress", ({ percent }) => {
  $("progress-bar").style.width = `${percent}%`;
});

// The machine going to sleep with a video running is not what anyone wants to
// come back to.
vesper.on("power:suspend", () => {
  if (state.playing) { $("player").pause(); setStatus("Paused — the system is suspending."); }
});

// Only fires when vesper-watch is installed; without it the user presses Refresh.
vesper.on("fs:changed", () => refresh());

// Native menu items reach the frontend as events.
vesper.on("menu:open_folder", openFolder);
vesper.on("menu:refresh", refresh);

applyCapabilities().then(() => setStatus("Ready. Open a folder to begin."));
