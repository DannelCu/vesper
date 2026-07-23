// Launcher frontend.
//
// The window arrives frameless, transparent and always-on-top. This wires the
// command palette, the two mini-apps (calculator + 2048), the global hotkey and
// the tray, and — the running theme of these examples — degrades every optional
// piece out loud: a capability that is missing greys out its command and says
// why, rather than offering a button that quietly does nothing.

(function () {
  "use strict";

  // Ctrl+Alt+Space is the classic launcher combo and also one of the most
  // contested — Claude Desktop and several IMEs take it. pynput observes keys
  // rather than grabbing them, so a clash is invisible: both apps just fire.
  // Hence a quieter default, and a Change button in Settings.
  var HOTKEY_DEFAULT = "ctrl+alt+k";
  var hotkey = HOTKEY_DEFAULT;
  var hotkeyError = "";      // why registration failed, if it did
  var hotkeyNote = "";       // non-fatal news, e.g. "fell back to the default"
  var capturingHotkey = false;

  var el = function (id) { return document.getElementById(id); };
  var caps = {};        // vesper.capabilities()
  var features = {};    // launcher:features (which plugins loaded)
  var visible = true;
  var lastResult = null; // last calculator value, for "Copy result"
  var mem = {};          // in-memory fallback when vesper.store is absent

  // vesper.capabilities() is a flat { name: boolean } map by design — the
  // framework keeps the install-instruction strings for whoever runs the app,
  // not the web UI. So the launcher carries its own short reasons for the UI.
  function cap(name) { return !!caps[name]; }

  var REASON = {
    screenshot: "needs vesper-screenshot (mss); unavailable on Wayland",
    clipboard_text: "clipboard backend missing — Linux needs xclip",
    global_shortcuts: "needs vesper-shortcuts (pynput)",
    tray: "needs the vesper[tray] extra (pystray + Pillow)",
    mica: "Windows 11 only",
    notifications: "no notification backend — Linux needs notify-send",
  };
  function reason(name) { return REASON[name] || "unavailable"; }

  // ── Hotkey accelerators ────────────────────────────────────────────────────
  //
  // The wire format is the plugin's: modifiers joined with "+", then the key —
  // a single character or a named key like space, enter, f2, up.

  var MOD_LABELS = { ctrl: "Ctrl", alt: "Alt", shift: "Shift", super: "Super", cmd: "Cmd" };

  function hotkeyLabel(accel) {
    return accel.split("+").map(function (part) {
      if (MOD_LABELS[part]) return MOD_LABELS[part];
      if (part.length === 1) return part.toUpperCase();
      return part.charAt(0).toUpperCase() + part.slice(1).replace(/_/g, " ");
    }).join(" + ");
  }

  // Turn a keydown into an accelerator, or null if it is not one yet — a bare
  // modifier while the user is still reaching for the second key, say.
  var NAMED_KEYS = {
    " ": "space", Enter: "enter", Tab: "tab", Backspace: "backspace",
    Delete: "delete", Insert: "insert", Home: "home", End: "end",
    PageUp: "page_up", PageDown: "page_down",
    ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right",
  };

  function accelFromEvent(e) {
    if (["Control", "Alt", "Shift", "Meta", "OS"].indexOf(e.key) !== -1) return null;

    var mods = [];
    if (e.ctrlKey) mods.push("ctrl");
    if (e.altKey) mods.push("alt");
    if (e.shiftKey) mods.push("shift");
    if (e.metaKey) mods.push("super");
    // A global hotkey with no modifier would swallow that key everywhere.
    if (!mods.length) return null;

    var key = NAMED_KEYS[e.key];
    if (!key && /^F\d{1,2}$/.test(e.key)) key = e.key.toLowerCase();
    if (!key && e.key.length === 1) key = e.key.toLowerCase();
    if (!key) return null;

    return mods.concat([key]).join("+");
  }

  function setStatus(msg, isError) {
    el("status").textContent = msg;
    document.querySelector(".footer").classList.toggle("error", !!isError);
  }

  // ── Persistence (vesper-store, or memory when the plugin is absent) ────────
  //
  // Gate on BOTH the JS namespace and features.store (the backend actually
  // loaded). The SDK file may have been synced once and left behind while the
  // Python plugin is uninstalled — in that case window.vesper.store exists but
  // its IPC commands are unregistered, so we would make failing round-trips.
  // storeReady, set in boot(), keeps us on the in-memory path instead.

  var storeReady = false;

  function sget(key, dflt) {
    if (storeReady) {
      return window.vesper.store.get(key).then(function (v) {
        return v === null || v === undefined ? dflt : v;
      }).catch(function () { return dflt; });
    }
    return Promise.resolve(key in mem ? mem[key] : dflt);
  }

  function sset(key, value) {
    if (storeReady) {
      return window.vesper.store.set(key, value).catch(function () {});
    }
    mem[key] = value;
    return Promise.resolve();
  }

  // ── Window presence: hide to tray, reappear top-centre ─────────────────────

  function reveal() {
    visible = true;
    return window.vesper.window.show().then(function () {
      // A launcher always lands in the same spot rather than where it was last
      // dragged: top-centre of the screen under the cursor, nudged down a little.
      return window.vesper.window.position("top-center", {
        screen: "cursor",
        offset: { y: 90 },
      });
    }).then(function () {
      showView("palette");
      var s = el("search");
      s.focus();
      s.select();
    });
  }

  function hide() {
    visible = false;
    // If there is a tray, hiding leaves the app reachable. Without one, hide()
    // still works but the only way back is the global hotkey — so the close
    // button falls back to quitting (see wireChrome).
    return window.vesper.window.hide();
  }

  function toggle() { return visible ? hide() : reveal(); }

  // ── Views ──────────────────────────────────────────────────────────────────

  var game = null;

  function showView(name) {
    ["palette", "calc", "game", "settings"].forEach(function (v) {
      el("view-" + v).hidden = v !== name;
    });
    if (name !== "game" && game) { game.destroy(); game = null; }
    if (name === "calc") { calcBuf = ""; renderCalcDisplay(); }
    if (name === "game") { startGame(); }
    if (name === "settings") { renderSettings(); }
    if (name === "palette") { el("search").focus(); }
  }

  function backToPalette() { showView("palette"); el("search").select(); }

  // ── Command palette ────────────────────────────────────────────────────────

  var selected = 0;
  var shown = [];

  function commands(query) {
    var q = query.trim();
    var webQuery = q.length > 0;
    var list = [
      { id: "calc", icon: "🧮", title: "Calculator",
        sub: "Evaluate an expression with a keypad", keys: "calculator maths math",
        run: function () { showView("calc"); } },
      { id: "game", icon: "🎮", title: "Play 2048",
        sub: "The slide-and-merge puzzle", keys: "2048 game play puzzle",
        run: function () { showView("game"); } },
      { id: "screenshot", icon: "📸", title: "Take a screenshot",
        sub: "Capture the screen to the captures folder", keys: "screenshot capture screen",
        available: features.screenshot && cap("screenshot"),
        reason: reason("screenshot"),
        run: runScreenshot },
      { id: "captures", icon: "🗂️", title: "Open captures folder",
        sub: "Reveal saved screenshots in the file manager", keys: "captures folder open screenshots",
        run: function () {
          return window.vesper.invoke("launcher:open_captures").then(function () {
            setStatus("Opened captures folder.");
          });
        } },
      { id: "copy", icon: "📋", title: "Copy last result",
        sub: lastResult === null ? "No result yet" : "Copy " + fmt(lastResult) + " to the clipboard",
        keys: "copy result clipboard",
        available: lastResult !== null && cap("clipboard_text"),
        reason: lastResult === null ? "run a calculation first" : reason("clipboard_text"),
        run: function () { return copyResult(); } },
      { id: "web", icon: "🌐", title: webQuery ? "Search the web for “" + q + "”" : "Search the web",
        sub: "Open your default browser", keys: "search web google duckduckgo",
        available: webQuery,
        reason: "type something to search for",
        run: function () {
          return window.vesper.shell.openUrl(
            "https://duckduckgo.com/?q=" + encodeURIComponent(q)
          ).then(function () { setStatus("Opened search in your browser."); hideIfReachable(); });
        } },
      { id: "settings", icon: "⚙️", title: "Settings",
        sub: "Hotkey, launch at login, capabilities", keys: "settings preferences hotkey autostart",
        run: function () { showView("settings"); } },
      { id: "quit", icon: "⏻", title: "Quit launcher",
        sub: "Close the app entirely", keys: "quit exit close",
        run: function () { return window.vesper.quit(); } },
    ];
    return list.map(function (c) {
      if (c.available === undefined) c.available = true;
      return c;
    });
  }

  function fmt(n) {
    // Trim binary-float dust (0.1 + 0.2) without lying about real precision.
    var r = Math.round(n * 1e10) / 1e10;
    return String(r);
  }

  function match(cmd, q) {
    if (!q) return true;
    var hay = (cmd.title + " " + cmd.keys).toLowerCase();
    return q.toLowerCase().split(/\s+/).every(function (tok) {
      return hay.indexOf(tok) !== -1;
    });
  }

  function refresh() {
    var query = el("search").value;
    var numeric = window.Calc.looksNumeric(query);
    var banner = el("calc-banner");

    if (numeric) {
      try {
        var value = window.Calc.evaluate(query);
        lastResult = value;
        el("calc-expr").textContent = query.trim();
        el("calc-value").textContent = fmt(value);
        banner.hidden = false;
        // When the query is maths, the palette narrows to what you do with a
        // number: copy it, or open the full calculator.
        shown = [
          { id: "copy", icon: "=", title: "Copy " + fmt(value),
            sub: "Put the result on the clipboard", available: cap("clipboard_text"),
            reason: reason("clipboard_text"),
            run: function () { return copyResult(); } },
          { id: "calc", icon: "🧮", title: "Open in Calculator",
            sub: "Keep working with a keypad", available: true,
            run: function () { showView("calc"); calcBuf = query.trim(); renderCalcDisplay(); } },
        ];
        selected = 0;
        renderResults();
        return;
      } catch (e) {
        // Half-typed maths ("12 *"): keep the banner out of the way and fall
        // through to the normal command list.
      }
    }

    banner.hidden = true;
    var all = commands(query);
    shown = all.filter(function (c) { return match(c, query); });
    // Available commands first; a disabled one stays listed (with its reason)
    // rather than vanishing, so the feature is discoverable.
    shown.sort(function (a, b) { return (a.available === b.available) ? 0 : (a.available ? -1 : 1); });
    selected = 0;
    renderResults();
  }

  function renderResults() {
    var ul = el("results");
    ul.innerHTML = "";
    shown.forEach(function (cmd, i) {
      var li = document.createElement("li");
      li.className = "result" + (cmd.available ? "" : " disabled");
      li.setAttribute("aria-selected", i === selected ? "true" : "false");
      li.innerHTML =
        '<span class="ico"></span><span class="txt">' +
        '<div class="title"></div><div class="sub"></div></span>';
      li.querySelector(".ico").textContent = cmd.icon;
      li.querySelector(".title").textContent = cmd.title;
      li.querySelector(".sub").textContent = cmd.available ? (cmd.sub || "") : cmd.reason;
      if (!cmd.available) {
        var badge = document.createElement("span");
        badge.className = "badge";
        badge.textContent = "unavailable";
        li.appendChild(badge);
      }
      li.addEventListener("click", function () { selected = i; run(cmd); });
      li.addEventListener("mousemove", function () {
        if (selected !== i) { selected = i; paintSelection(); }
      });
      ul.appendChild(li);
    });
  }

  function paintSelection() {
    var items = el("results").children;
    for (var i = 0; i < items.length; i++) {
      items[i].setAttribute("aria-selected", i === selected ? "true" : "false");
    }
    if (items[selected]) items[selected].scrollIntoView({ block: "nearest" });
  }

  function run(cmd) {
    if (!cmd || !cmd.available) {
      if (cmd) setStatus(cmd.title + " — " + cmd.reason, true);
      return;
    }
    remember(cmd.id);
    Promise.resolve(cmd.run()).catch(function (err) {
      setStatus(err.message || String(err), true);
    });
  }

  function remember(id) {
    sget("recent", []).then(function (recent) {
      recent = [id].concat(recent.filter(function (x) { return x !== id; })).slice(0, 5);
      sset("recent", recent);
    });
  }

  // ── Calculator (keypad view) ───────────────────────────────────────────────

  var calcBuf = "";

  function renderCalcDisplay() { el("calc-display").textContent = calcBuf || "0"; }

  function calcEval() {
    try {
      var v = window.Calc.evaluate(calcBuf);
      lastResult = v;
      calcBuf = fmt(v);
      renderCalcDisplay();
      setStatus("= " + fmt(v));
    } catch (e) {
      setStatus(e.message, true);
    }
  }

  function copyResult() {
    if (lastResult === null) { setStatus("No result to copy yet.", true); return Promise.resolve(); }
    if (!cap("clipboard_text")) { setStatus("Clipboard unavailable: " + reason("clipboard_text"), true); return Promise.resolve(); }
    return window.vesper.clipboard.write(fmt(lastResult)).then(function () {
      setStatus("Copied " + fmt(lastResult) + " to the clipboard.");
      hideIfReachable();
    });
  }

  // Getting out of the way after an action is the launcher gesture — but only
  // when there is a way back. With neither a tray icon nor a global hotkey,
  // hiding would strand the window with nothing to summon it, so stay visible.
  function canBeSummoned() {
    return cap("tray") || (features.shortcuts && cap("global_shortcuts"));
  }

  // hide() removes the window from the taskbar entirely, so with nothing to
  // summon it the app would be unreachable. Minimizing instead gets it out of the
  // way while leaving a taskbar entry to click.
  function hideIfReachable() {
    visible = false;
    return canBeSummoned() ? hide() : window.vesper.window.minimize();
  }

  function wireCalc() {
    document.querySelectorAll("#view-calc .keypad button").forEach(function (b) {
      b.addEventListener("click", function () {
        if (b.dataset.op === "clear") { calcBuf = ""; }
        else if (b.dataset.op === "back") { calcBuf = calcBuf.slice(0, -1); }
        else { calcBuf += b.dataset.key; }
        renderCalcDisplay();
      });
    });
    el("calc-eval").addEventListener("click", calcEval);
    el("calc-copy").addEventListener("click", copyResult);
  }

  // ── 2048 ────────────────────────────────────────────────────────────────────

  function startGame() {
    sget("best2048", 0).then(function (best) {
      el("best").textContent = best;
      game = window.Game2048.create(el("game-mount"), {
        best: best,
        onScore: function (score, newBest) {
          el("score").textContent = score;
          el("best").textContent = newBest;
          if (newBest > best) { best = newBest; sset("best2048", newBest); }
        },
      });
      el("game-mount").focus();
    });
  }

  var GAME_KEYS = {
    ArrowLeft: "left", ArrowRight: "right", ArrowUp: "up", ArrowDown: "down",
    a: "left", d: "right", w: "up", s: "down",
  };

  // ── Screenshot ──────────────────────────────────────────────────────────────

  function runScreenshot() {
    if (!features.screenshot || !cap("screenshot")) {
      setStatus("Screenshot unavailable: " + reason("screenshot"), true);
      return;
    }
    // Get the launcher out of its own shot, then capture — and always come back,
    // on success and on failure alike. A window that hides itself for an action
    // and never returns is indistinguishable from one that crashed, and an error
    // painted onto a hidden window is an error nobody reads.
    return hide().then(function () {
      return new Promise(function (res) { setTimeout(res, 280); });
    }).then(function () {
      return window.vesper.invoke("launcher:new_capture_path");
    }).then(function (dest) {
      return window.vesper.screenshot.captureToFile(dest);
    }).then(function (path) {
      // vesper.notify(title, body) is a function, not a namespace — see
      // docs/notifications.md. Notifications are a nicety: a missing backend
      // must not turn a capture that already succeeded into a failure.
      if (cap("notifications")) {
        window.vesper.notify("Launcher", "Saved " + path).catch(function () {});
      }
      return reveal().then(function () { setStatus("Screenshot saved to " + path); });
    }).catch(function (err) {
      return reveal().then(function () {
        setStatus("Screenshot failed: " + (err.message || err), true);
      });
    });
  }

  // ── Settings ────────────────────────────────────────────────────────────────

  function renderHotkeySetting() {
    var detail = el("hotkey-detail");
    var button = el("hotkey-rebind");

    if (!hotkeyAvailable()) {
      detail.textContent =
        "Not active — " + reason("global_shortcuts") +
        ". Use the tray or relaunch to reopen.";
      button.disabled = true;
      button.textContent = "Change";
      return;
    }

    button.disabled = false;
    if (capturingHotkey) {
      detail.textContent = "Press the new combination — Esc to cancel.";
      button.textContent = "Listening…";
    } else if (hotkeyError) {
      detail.textContent = "Could not register a hotkey: " + hotkeyError;
      button.textContent = "Change";
    } else {
      detail.textContent =
        "Press " + hotkeyLabel(hotkey) + " anywhere to show or hide the launcher." +
        (hotkeyNote ? " " + hotkeyNote : "") +
        " Nothing can tell you if another app already uses it: both will fire.";
      button.textContent = "Change";
    }
  }

  function startHotkeyCapture() {
    if (!hotkeyAvailable() || capturingHotkey) return;
    capturingHotkey = true;
    renderHotkeySetting();
  }

  function finishHotkeyCapture(accel) {
    capturingHotkey = false;
    if (!accel) { renderHotkeySetting(); return; }

    bindHotkey(accel).then(function (err) {
      if (err) {
        setStatus("Could not use that combination: " + err, true);
      } else {
        hotkeyNote = "";
        setStatus("Hotkey is now " + hotkeyLabel(accel) + ".");
        sset("hotkey", accel);
      }
      renderHotkeySetting();
      el("footer-hint").textContent = footerHint();
    });
  }

  function renderSettings() {
    renderHotkeySetting();

    // Launch at login
    window.vesper.autostart.isEnabled().then(function (on) {
      var btn = el("autostart-toggle");
      btn.disabled = false;
      btn.textContent = on ? "Disable" : "Enable";
      el("autostart-detail").textContent = on
        ? "The launcher starts when you log in."
        : "The launcher does not start at login.";
      btn.onclick = function () {
        var p = on ? window.vesper.autostart.disable() : window.vesper.autostart.enable();
        p.then(function (ok) {
          if (!ok && !on) {
            el("autostart-detail").textContent =
              "Only applies to a packaged build — running from source there is no app to launch.";
          } else {
            renderSettings();
          }
        });
      };
    });

    // Capability table
    var ul = el("caps-list");
    ul.innerHTML = "";
    var rows = [
      ["Global hotkey", features.shortcuts && cap("global_shortcuts"), reason("global_shortcuts")],
      ["Tray", cap("tray"), reason("tray")],
      ["Mica/acrylic", cap("mica"), reason("mica")],
      ["Screenshot", features.screenshot && cap("screenshot"), reason("screenshot")],
      ["Clipboard", cap("clipboard_text"), reason("clipboard_text")],
      ["Persistent store", features.store, features.store ? "vesper-store" : "install vesper-store"],
      ["Notifications", cap("notifications"), reason("notifications")],
    ];
    rows.forEach(function (r) {
      var li = document.createElement("li");
      var ok = !!r[1];
      li.innerHTML =
        '<span class="dot ' + (ok ? "ok" : "no") + '">' + (ok ? "●" : "○") + "</span>" +
        '<span class="cname"></span><span class="cdetail"></span>';
      li.querySelector(".cname").textContent = r[0];
      li.querySelector(".cdetail").textContent = ok ? "" : (r[2] || "");
      ul.appendChild(li);
    });
  }

  // ── Chrome, backdrop, hotkey, tray ─────────────────────────────────────────

  function wireChrome() {
    el("btn-settings").addEventListener("click", function () { showView("settings"); });
    el("btn-hide").addEventListener("click", function () { hideIfReachable(); });
    el("btn-close").addEventListener("click", function () {
      // With a tray the launcher lives on after "closing"; without one, there is
      // nothing to reopen it from a hidden state except the hotkey, so honour the
      // × as a real quit.
      if (cap("tray")) { hide(); } else { window.vesper.quit(); }
    });
    el("hotkey-rebind").addEventListener("click", startHotkeyCapture);
    document.querySelectorAll("[data-back]").forEach(function (b) {
      b.addEventListener("click", backToPalette);
    });
  }

  function applyBackdrop() {
    // Windows 11 only; a no-op everywhere else. The translucent panel (CSS
    // backdrop-filter) is the look on platforms without a native material.
    if (cap("mica")) {
      window.vesper.window.setBackdrop("acrylic").catch(function () {});
    }
  }

  function hotkeyAvailable() {
    return !!(features.shortcuts && cap("global_shortcuts"));
  }

  function footerHint() {
    if (!hotkeyAvailable()) return "Global hotkey off — see Settings";
    if (hotkeyError) return "Hotkey failed — see Settings";
    return hotkeyLabel(hotkey) + " toggles the launcher";
  }

  // Register `accel`, dropping whatever was bound before. Resolves to "" on
  // success or the failure message — the old code swallowed the rejection, so a
  // hotkey that could not be registered still advertised itself in Settings.
  function bindHotkey(accel) {
    if (!hotkeyAvailable()) return Promise.resolve("");

    var previous = hotkey;
    return window.vesper.shortcuts.register(accel).then(function () {
      if (previous && previous !== accel) {
        return window.vesper.shortcuts.unregister(previous).catch(function () {});
      }
    }).then(function () {
      hotkey = accel;
      hotkeyError = "";
      return "";
    }).catch(function (err) {
      hotkeyError = err.message || String(err);
      return hotkeyError;
    });
  }

  function wireHotkey() {
    window.vesper.on("shortcut", function () { toggle(); });
    if (!hotkeyAvailable()) return Promise.resolve();

    return sget("hotkey", HOTKEY_DEFAULT).then(function (saved) {
      return bindHotkey(saved).then(function (err) {
        // A saved accelerator the plugin will not take (edited by hand, or a
        // key this pynput build does not know) must not leave the launcher with
        // no hotkey at all — fall back to the default that ships with it.
        if (err && saved !== HOTKEY_DEFAULT) {
          return bindHotkey(HOTKEY_DEFAULT).then(function (fallbackErr) {
            if (!fallbackErr) {
              hotkeyNote = "Your saved " + hotkeyLabel(saved) +
                " was rejected, so the default is back.";
            }
          });
        }
      });
    });
  }

  function wireTray() {
    // Tray menu items run on a background thread and only emit events; the
    // window work happens here, on the GUI thread.
    window.vesper.on("tray:reveal", function () { reveal(); });
    window.vesper.on("tray:screenshot", function () { runScreenshot(); });
  }

  // ── Keyboard ────────────────────────────────────────────────────────────────

  function onKeyDown(e) {
    // Rebinding swallows everything: while listening, Esc means "cancel", not
    // "hide the launcher", and Enter must not run the selected command.
    if (capturingHotkey) {
      e.preventDefault();
      if (e.key === "Escape") { finishHotkeyCapture(null); return; }
      var accel = accelFromEvent(e);
      if (accel) finishHotkeyCapture(accel);
      return;
    }

    var palette = !el("view-palette").hidden;
    var gameView = !el("view-game").hidden;
    var calcView = !el("view-calc").hidden;

    if (e.key === "Escape") {
      if (palette) { hideIfReachable(); } else { backToPalette(); }
      e.preventDefault();
      return;
    }

    if (palette) {
      if (e.key === "ArrowDown") { selected = Math.min(selected + 1, shown.length - 1); paintSelection(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { selected = Math.max(selected - 1, 0); paintSelection(); e.preventDefault(); }
      else if (e.key === "Enter") { run(shown[selected]); e.preventDefault(); }
      return;
    }

    if (gameView && GAME_KEYS[e.key] && game) {
      game.move(GAME_KEYS[e.key]);
      e.preventDefault();
      return;
    }

    if (calcView) {
      if (e.key === "Enter") { calcEval(); e.preventDefault(); }
      else if (e.key === "Backspace") { calcBuf = calcBuf.slice(0, -1); renderCalcDisplay(); e.preventDefault(); }
      else if ("0123456789.+-*/%^()".indexOf(e.key) !== -1) { calcBuf += e.key; renderCalcDisplay(); e.preventDefault(); }
    }
  }

  // ── Boot ────────────────────────────────────────────────────────────────────

  function boot() {
    Promise.all([
      window.vesper.invoke("launcher:features"),
      window.vesper.capabilities(),
    ]).then(function (r) {
      features = r[0];
      caps = r[1];
      storeReady = !!(features.store && window.vesper.store);

      wireChrome();
      wireCalc();
      wireTray();
      applyBackdrop();

      el("search").addEventListener("input", refresh);
      el("game-new").addEventListener("click", function () { if (game) game.restart(); });
      document.addEventListener("keydown", onKeyDown);

      refresh();
      reveal();

      // The footer can only name the hotkey once we know which one took.
      return wireHotkey().then(function () {
        el("footer-hint").textContent = footerHint();
      });
    }).catch(function (err) {
      setStatus("Failed to start: " + (err.message || err), true);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
