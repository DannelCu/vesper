(function (global) {
    let nextRequestId = 1;

    function createRequestId() {
        return nextRequestId++;
    }

    async function waitForPyWebView() {
        if (global.pywebview && global.pywebview.api) {
            return;
        }

        await new Promise((resolve) => {
            global.addEventListener("pywebviewready", resolve, {once: true});
        });
    }

    async function invoke(command, args = {}) {
        if (!command || typeof command !== "string") {
            throw new TypeError("vesper.invoke(command, args) requires a command name string.");
        }

        await waitForPyWebView();

        const request = {
            id: createRequestId(),
            command,
            args
        };

        const response = await global.pywebview.api.invoke(JSON.stringify(request));

        if (!response || typeof response !== "object") {
            throw new Error("Invalid response received from Vesper.");
        }

        if (!response.ok) {
            const error = response.error || {};
            const errorMessage = error.message || "Unknown Vesper error.";
            const errorType = error.type || "VesperError";

            const exception = new Error(errorMessage);
            exception.name = errorType;
            exception.details = error;

            throw exception;
        }

        return response.result;
    }

    function on(event, handler) {
        const wrapped = function(e) { handler(e.detail); };
        window.addEventListener("vesper:" + event, wrapped);
        return function() {
            window.removeEventListener("vesper:" + event, wrapped);
        };
    }

    var dialog = {
        /**
         * Open a native file-picker dialog.
         * @param {object} [options]
         * @param {boolean} [options.multiple=false]
         * @param {{name:string,extensions:string[]}[]} [options.filters]
         * @param {string} [options.directory=""]
         * @returns {Promise<string[]|null>}
         */
        open: function(options) {
            return invoke("vesper:dialog:open", options || {});
        },
        /**
         * Open a native save-file dialog.
         * @param {object} [options]
         * @param {string} [options.filename=""]
         * @param {{name:string,extensions:string[]}[]} [options.filters]
         * @param {string} [options.directory=""]
         * @returns {Promise<string|null>}
         */
        save: function(options) {
            return invoke("vesper:dialog:save", options || {});
        },
        /**
         * Open a native folder-picker dialog.
         * @param {object} [options]
         * @param {string} [options.directory=""]
         * @param {boolean} [options.multiple=false]
         * @returns {Promise<string[]|null>}
         */
        pickFolder: function(options) {
            return invoke("vesper:dialog:folder", options || {});
        },
        /**
         * Show a native message dialog with a single acknowledgement button.
         * @param {string} message
         * @param {string} [title]
         * @returns {Promise<void>}
         */
        message: function(message, title) {
            return invoke("vesper:dialog:message", { title: title || "", message: message || "" });
        },
        /**
         * Ask the user to confirm an action.
         * @param {string} message
         * @param {string} [title]
         * @returns {Promise<boolean>} True when confirmed.
         */
        confirm: function(message, title) {
            return invoke("vesper:dialog:confirm", { title: title || "", message: message || "" });
        },
        /**
         * Ask the user a yes/no question. Same dialog as confirm(), named for
         * questions rather than for confirming a pending action.
         * @param {string} message
         * @param {string} [title]
         * @returns {Promise<boolean>}
         */
        ask: function(message, title) {
            return invoke("vesper:dialog:ask", { title: title || "", message: message || "" });
        },
    };

    function notify(title, body) {
        return invoke("vesper:notify", { title: title || "", body: body || "" });
    }

    var fs = {
        /**
         * Read a file and return its contents as a string.
         * @param {string} path
         * @param {string} [encoding="utf-8"]
         * @returns {Promise<string>}
         */
        read: function(path, encoding) {
            return invoke("vesper:fs:read", { path: path, encoding: encoding || "utf-8" });
        },
        /**
         * Write a string to a file (creates parent directories if needed).
         * @param {string} path
         * @param {string} content
         * @param {string} [encoding="utf-8"]
         * @returns {Promise<void>}
         */
        write: function(path, content, encoding) {
            return invoke("vesper:fs:write", { path: path, content: content, encoding: encoding || "utf-8" });
        },
        /**
         * Return true if the path exists.
         * @param {string} path
         * @returns {Promise<boolean>}
         */
        exists: function(path) {
            return invoke("vesper:fs:exists", { path: path });
        },
        /**
         * List entries in a directory.
         * @param {string} path
         * @returns {Promise<{name:string, path:string, is_dir:boolean}[]>}
         */
        list: function(path) {
            return invoke("vesper:fs:list", { path: path });
        },
        /**
         * Move a file or directory to the system trash.
         *
         * Recoverable, unlike a delete. Rejects rather than falling back to a
         * permanent delete when no trash backend is available.
         * @param {string} path
         * @returns {Promise<boolean>}
         */
        trash: function(path) {
            return invoke("vesper:fs:trash", { path: path });
        },
        /**
         * Create a directory. Fails if it already exists.
         * @param {string} path
         * @param {boolean} [parents=false] - Also create missing ancestors.
         * @returns {Promise<void>}
         */
        mkdir: function(path, parents) {
            return invoke("vesper:fs:mkdir", { path: path, parents: !!parents });
        },
        /**
         * Copy a file or directory tree. Both ends honour the fs scope.
         * @param {string} src
         * @param {string} dst
         * @returns {Promise<void>}
         */
        copy: function(src, dst) {
            return invoke("vesper:fs:copy", { src: src, dst: dst });
        },
        /**
         * Move (or rename) a file or directory. Both ends honour the fs scope.
         * @param {string} src
         * @param {string} dst
         * @returns {Promise<void>}
         */
        move: function(src, dst) {
            return invoke("vesper:fs:move", { src: src, dst: dst });
        },
        /**
         * Delete a file, permanently. Directories require recursive=true —
         * for anything the user might want back, use trash() instead.
         * @param {string} path
         * @param {boolean} [recursive=false]
         * @returns {Promise<void>}
         */
        remove: function(path, recursive) {
            return invoke("vesper:fs:remove", { path: path, recursive: !!recursive });
        },
        /**
         * File metadata.
         * @param {string} path
         * @returns {Promise<{size:number, mtime:number, is_dir:boolean, type:string}>}
         */
        stat: function(path) {
            return invoke("vesper:fs:stat", { path: path });
        },
        /**
         * Read a file's raw bytes as base64 — the canonical way to move binary
         * data across the JSON IPC bridge.
         * @param {string} path
         * @returns {Promise<string>} Base64-encoded contents.
         */
        readBytes: function(path) {
            return invoke("vesper:fs:read_bytes", { path: path });
        },
        /**
         * Write base64-encoded data to a file as raw bytes (creates parent
         * directories if needed).
         * @param {string} path
         * @param {string} data - Base64-encoded bytes.
         * @returns {Promise<void>}
         */
        writeBytes: function(path, data) {
            return invoke("vesper:fs:write_bytes", { path: path, data: data });
        },
    };

    var autostart = {
        /**
         * Launch this app when the user logs in.
         *
         * Only meaningful for a packaged app: running from source it resolves to
         * the Python interpreter, so it is a no-op and resolves false.
         * @returns {Promise<boolean>}
         */
        enable: function() { return invoke("vesper:autostart:enable", {}); },
        /** Stop launching at login. @returns {Promise<boolean>} */
        disable: function() { return invoke("vesper:autostart:disable", {}); },
        /** Whether launch-at-login is currently registered. @returns {Promise<boolean>} */
        isEnabled: function() { return invoke("vesper:autostart:is_enabled", {}); },
    };

    var power = {
        /**
         * Keep the system and display awake until allowSleep() is called.
         *
         * Resolves false when the platform offers no way to do it, so a caller
         * that cares can tell "held" from "unavailable".
         * @param {string} [reason] - Shown by the OS where it surfaces inhibitors.
         * @returns {Promise<boolean>}
         */
        preventSleep: function(reason) {
            return invoke("vesper:power:prevent_sleep", { reason: reason || "Vesper app is busy" });
        },
        /** Release a previous preventSleep(). @returns {Promise<boolean>} */
        allowSleep: function() { return invoke("vesper:power:allow_sleep", {}); },
    };

    /**
     * Which optional backends are available on this machine.
     *
     * Vesper's optional features degrade to no-ops when their backend is missing —
     * on a Linux box without xclip, `clipboard.readImage()` simply resolves null.
     * Ask first so the UI can hide or disable the control instead of offering a
     * button that does nothing.
     *
     *   const caps = await vesper.capabilities()
     *   pasteButton.hidden = !caps.clipboard_image
     *
     * Keys: clipboard_text, clipboard_image, clipboard_files, notifications,
     * trash, keep_awake, tray, badge, mica, nsis, power_events,
     * global_shortcuts. Each is a boolean.
     *
     * @returns {Promise<Object<string, boolean>>}
     */
    function capabilities() {
        return invoke("vesper:capabilities", {});
    }

    var security = {
        /**
         * Turn off browser behaviours that make a desktop app feel like a web page.
         *
         * Opt-in and off in dev: reload and devtools are exactly what you want while
         * building. Detection is via the dev server URL, so a production build with
         * no dev server locks down and `vesper dev` never does.
         *
         * Each flag is independent and defaults to true:
         *
         *   reload       F5, Ctrl/Cmd+R, Ctrl/Cmd+Shift+R
         *   find         Ctrl/Cmd+F, and Ctrl/Cmd+G
         *   contextMenu  right-click menu — still allowed in inputs and textareas
         *                unless allowContextMenuInInputs is false, since cut/paste
         *                there is a real loss
         *   zoom         Ctrl+scroll and Ctrl/Cmd +/-/0
         *   selection    text selection outside inputs; off by default because it
         *                breaks copying from the UI, which users do expect
         *   print        Ctrl/Cmd+P
         *
         * @param {object} [options]
         * @returns {function} Call it to undo the lockdown.
         */
        lockdown: function(options) {
            var opts = options || {};

            function on(name, fallback) {
                return opts[name] === undefined ? fallback : !!opts[name];
            }

            var cfg = {
                reload: on("reload", true),
                find: on("find", true),
                contextMenu: on("contextMenu", true),
                zoom: on("zoom", true),
                selection: on("selection", false),
                print: on("print", true),
                allowContextMenuInInputs: on("allowContextMenuInInputs", true),
                force: on("force", false),
            };

            // VESPER_DEV_URL is what the dev server sets; skip unless told otherwise.
            var isDev = !!(global.VESPER_DEV_URL ||
                (global.location && /^https?:/.test(global.location.protocol) &&
                 /localhost|127\.0\.0\.1/.test(global.location.hostname)));

            if (isDev && !cfg.force) {
                return function() {};
            }

            function isEditable(el) {
                if (!el) return false;
                var tag = (el.tagName || "").toLowerCase();
                return tag === "input" || tag === "textarea" || el.isContentEditable;
            }

            function onKeyDown(e) {
                var mod = e.ctrlKey || e.metaKey;
                var key = (e.key || "").toLowerCase();

                if (cfg.reload && (key === "f5" || (mod && key === "r"))) {
                    e.preventDefault();
                    return;
                }
                if (cfg.find && mod && (key === "f" || key === "g")) {
                    e.preventDefault();
                    return;
                }
                if (cfg.print && mod && key === "p") {
                    e.preventDefault();
                    return;
                }
                if (cfg.zoom && mod && (key === "+" || key === "-" || key === "=" || key === "0")) {
                    e.preventDefault();
                }
            }

            function onContextMenu(e) {
                if (cfg.allowContextMenuInInputs && isEditable(e.target)) return;
                e.preventDefault();
            }

            function onWheel(e) {
                if (e.ctrlKey) e.preventDefault();
            }

            function onSelectStart(e) {
                if (!isEditable(e.target)) e.preventDefault();
            }

            var listeners = [];

            function add(target, type, fn, opts2) {
                target.addEventListener(type, fn, opts2);
                listeners.push([target, type, fn, opts2]);
            }

            add(global, "keydown", onKeyDown);
            if (cfg.contextMenu) add(global, "contextmenu", onContextMenu);
            // passive:false is required or preventDefault() on wheel is ignored.
            if (cfg.zoom) add(global, "wheel", onWheel, { passive: false });
            if (cfg.selection) add(global, "selectstart", onSelectStart);

            return function undo() {
                for (var i = 0; i < listeners.length; i++) {
                    var l = listeners[i];
                    l[0].removeEventListener(l[1], l[2], l[3]);
                }
                listeners = [];
            };
        },
    };

    var badge = {
        /**
         * Show a progress bar on the taskbar button or dock icon.
         *
         * Support is uneven — resolves false where the platform cannot do it, so
         * treat it as a nicety rather than something to depend on.
         * @param {number} fraction - 0.0 to 1.0, clamped.
         * @returns {Promise<boolean>}
         */
        setProgress: function(fraction) {
            return invoke("vesper:badge:set_progress", { fraction: fraction });
        },
        /** Remove the progress indicator. @returns {Promise<boolean>} */
        clearProgress: function() { return invoke("vesper:badge:clear_progress", {}); },
        /**
         * Show a count on the dock or launcher icon. 0 clears it.
         * Not supported on Windows.
         * @param {number} count
         * @returns {Promise<boolean>}
         */
        setBadge: function(count) {
            return invoke("vesper:badge:set_badge", { count: count });
        },
        /** Remove the count. @returns {Promise<boolean>} */
        clearBadge: function() { return invoke("vesper:badge:clear_badge", {}); },
    };

    var window_controls = {
        /** Minimize the application window. @returns {Promise<void>} */
        minimize: function() { return invoke("vesper:window:minimize", {}); },
        /** Maximize the application window. @returns {Promise<void>} */
        maximize: function() { return invoke("vesper:window:maximize", {}); },
        /** Restore the window from minimized or maximized state. @returns {Promise<void>} */
        restore: function() { return invoke("vesper:window:restore", {}); },
        /**
         * Hide the window without destroying it.
         *
         * Unlike minimize(), this removes the window from the taskbar and
         * alt-tab — the pattern for a tray app or launcher that "closes" to
         * the tray and reappears on a hotkey or tray click. Bring it back
         * with show().
         * @returns {Promise<void>}
         */
        hide: function() { return invoke("vesper:window:hide", {}); },
        /** Show the window again after hide(). @returns {Promise<void>} */
        show: function() { return invoke("vesper:window:show", {}); },
        /** Toggle fullscreen mode. @returns {Promise<void>} */
        fullscreen: function() { return invoke("vesper:window:fullscreen", {}); },
        /**
         * Resize the window.
         * @param {number} width
         * @param {number} height
         * @returns {Promise<void>}
         */
        resize: function(width, height) {
            return invoke("vesper:window:resize", { width: width, height: height });
        },
        /**
         * Move the window to the given screen coordinates.
         * @param {number} x
         * @param {number} y
         * @returns {Promise<void>}
         */
        move: function(x, y) {
            return invoke("vesper:window:move", { x: x, y: y });
        },
        /**
         * Move the window to a semantic position on a monitor.
         *
         * Positions: top-left, top-center, top-right, center-left, center,
         * center-right, bottom-left, bottom-center, bottom-right.
         *
         * @param {string} position
         * @param {object} [options]
         * @param {number|string} [options.screen] - Screen index, or "cursor"
         *        for the monitor under the cursor (falls back to the primary
         *        where the platform cannot say — Linux).
         * @param {{x:number, y:number}} [options.offset] - Added as-is; use
         *        negatives to pull a bottom/right-anchored window off the edge.
         * @returns {Promise<void>}
         */
        position: function(position, options) {
            var opts = options || {};
            var offset = opts.offset || {};
            return invoke("vesper:window:position", {
                position: position,
                screen: opts.screen === undefined ? null : opts.screen,
                offset_x: offset.x || 0,
                offset_y: offset.y || 0
            });
        },
        /**
         * Apply a Windows 11 backdrop material to the window.
         *
         * Cosmetic and best-effort: resolves false on any platform or build
         * that cannot apply it. Check vesper.capabilities().mica first.
         * @param {string} [kind="mica"] - "mica", "acrylic", "tabbed", or "none".
         * @returns {Promise<boolean>}
         */
        setBackdrop: function(kind) {
            return invoke("vesper:window:set_backdrop", { kind: kind || "mica" });
        },
        /**
         * Make an element a drag region for a frameless window.
         *
         * The functional equivalent of -webkit-app-region: drag. Use with
         * App(frameless=True, easy_drag=False) and mark your custom titlebar
         * as draggable; interactive children (buttons) stay clickable.
         * Elements carrying the data-vesper-drag attribute are wired
         * automatically on load — this helper is for elements created later.
         *
         * @param {Element|string} target - Element or CSS selector.
         * @returns {function():void} Undo function.
         */
        makeDraggable: function(target) {
            var els = typeof target === "string"
                ? Array.prototype.slice.call(document.querySelectorAll(target))
                : [target];
            for (var i = 0; i < els.length; i++) {
                // PyWebView's built-in drag region marker class.
                els[i].classList.add("pywebview-drag-region");
            }
            return function undo() {
                for (var j = 0; j < els.length; j++) {
                    els[j].classList.remove("pywebview-drag-region");
                }
            };
        },
    };

    function wireDeclaredDragRegions() {
        var els = document.querySelectorAll("[data-vesper-drag]");
        for (var i = 0; i < els.length; i++) {
            els[i].classList.add("pywebview-drag-region");
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", wireDeclaredDragRegions);
    } else {
        wireDeclaredDragRegions();
    }

    var screen = {
        /**
         * Return info for all connected screens.
         * @returns {Promise<{width:number, height:number, x:number, y:number}[]>}
         */
        list: function() { return invoke("vesper:screen:list", {}); },
    };

    var os = {
        /**
         * Return OS platform info.
         * @returns {Promise<{platform:string, version:string, machine:string, python_version:string}>}
         */
        info: function() { return invoke("vesper:os:info", {}); },
    };

    function quit() {
        return invoke("vesper:app:quit", {});
    }

    var drop = {
        /**
         * Attach a file-drop listener to an element.
         * Calls callback(files, event) when files are dropped.
         * @param {Element} element
         * @param {function(FileList, DragEvent):void} callback
         * @returns {function():void} Unsubscribe function.
         */
        onFiles: function(element, callback) {
            function onDragOver(e) { e.preventDefault(); }
            function onDrop(e) {
                e.preventDefault();
                callback(e.dataTransfer.files, e);
            }
            element.addEventListener("dragover", onDragOver);
            element.addEventListener("drop", onDrop);
            return function() {
                element.removeEventListener("dragover", onDragOver);
                element.removeEventListener("drop", onDrop);
            };
        },
    };

    var shell = {
        /**
         * Open a URL in the default system browser.
         * @param {string} url
         * @returns {Promise<void>}
         */
        openUrl: function(url) {
            return invoke("vesper:shell:open_url", { url: url });
        },
        /**
         * Reveal a file or folder in the native file manager.
         * @param {string} path - Absolute path to the file or folder.
         * @returns {Promise<void>}
         */
        reveal: function(path) {
            return invoke("vesper:shell:reveal", { path: path });
        },
    };

    var clipboard = {
        /**
         * Read text from the system clipboard.
         * @returns {Promise<string>}
         */
        read: function() {
            return invoke("vesper:clipboard:read", {});
        },
        /**
         * Write text to the system clipboard.
         * @param {string} text
         * @returns {Promise<void>}
         */
        write: function(text) {
            return invoke("vesper:clipboard:write", { text: text });
        },
        /**
         * Read an image from the clipboard as a PNG data URL, usable directly as
         * an <img src>. Resolves null when the clipboard holds no image.
         * @returns {Promise<string|null>}
         */
        readImage: function() {
            return invoke("vesper:clipboard:read_image", {});
        },
        /**
         * Put a PNG on the clipboard.
         * @param {string} dataUrl - "data:image/png;base64,..." or bare base64.
         * @returns {Promise<boolean>}
         */
        writeImage: function(dataUrl) {
            return invoke("vesper:clipboard:write_image", { data_url: dataUrl });
        },
        /**
         * Put files on the clipboard as the OS file object — after this,
         * Paste in Explorer/Finder/the file manager copies the files.
         * Check vesper.capabilities().clipboard_files first.
         * @param {string[]} paths - Absolute paths.
         * @returns {Promise<boolean>}
         */
        writeFiles: function(paths) {
            return invoke("vesper:clipboard:write_files", { paths: paths });
        },
        /**
         * File paths currently on the clipboard (after Copy in the file
         * manager). Paths outside the app's fs scope are filtered out.
         * On macOS at most one path is returned — platform limitation.
         * @returns {Promise<string[]>}
         */
        readFiles: function() {
            return invoke("vesper:clipboard:read_files", {});
        },
    };

    var netDownloadId = 1;

    var net = {
        /**
         * Download a file to a destination path with progress.
         *
         * The destination honours the app's fs scope like every other write.
         * Not an HTTP client — for headers, JSON, and sessions use the
         * vesper-http plugin; this streams large files straight to disk.
         *
         * @param {string} url
         * @param {string} dest - Destination file path.
         * @param {function(number):void} [onProgress] - Called with 0–100.
         * @param {string} [sha256] - Optional expected SHA-256; mismatch rejects
         *                            and deletes the file.
         * @returns {Promise<string>} The destination path.
         */
        download: function(url, dest, onProgress, sha256) {
            var id = "net-" + (netDownloadId++);
            var unsub;
            if (typeof onProgress === "function") {
                unsub = on("net:progress", function(data) {
                    if (data.id === id) onProgress(data.percent);
                });
            }
            return invoke("vesper:net:download", {
                url: url, dest: dest, sha256: sha256 || "", id: id
            }).then(
                function(result) {
                    if (unsub) unsub();
                    return result;
                },
                function(err) {
                    if (unsub) unsub();
                    throw err;
                }
            );
        },
    };

    var processNs = {
        /**
         * Run a command to completion and capture its output.
         *
         * Only executables the app declared in App(shell_scope=...) can run;
         * everything else rejects before a process is created. A nonzero exit
         * code resolves normally — inspect `code` to decide what failure means.
         *
         * @param {string[]} argv - Executable and arguments as a list.
         * @param {object} [options]
         * @param {string} [options.cwd]
         * @param {number} [options.timeout] - Seconds; the process is killed on expiry.
         * @returns {Promise<{code:number, stdout:string, stderr:string}>}
         */
        run: function(argv, options) {
            var opts = options || {};
            return invoke("vesper:process:run", {
                argv: argv,
                cwd: opts.cwd || "",
                timeout: opts.timeout || 0
            });
        },
        /**
         * Start a long-running process and stream its output.
         *
         * stdout/stderr arrive line by line through the handlers; onExit fires
         * once, after the last line, and cleans up the subscriptions.
         *
         * @param {string[]} argv
         * @param {object} [handlers]
         * @param {string} [handlers.cwd]
         * @param {function(string):void} [handlers.onStdout]
         * @param {function(string):void} [handlers.onStderr]
         * @param {function(number):void} [handlers.onExit]
         * @returns {Promise<{id:number, kill:function():Promise<boolean>}>}
         */
        spawn: function(argv, handlers) {
            var h = handlers || {};
            return invoke("vesper:process:spawn", { argv: argv, cwd: h.cwd || "" })
                .then(function(id) {
                    var unsubs = [];

                    function line(event, cb) {
                        if (typeof cb !== "function") return;
                        unsubs.push(on("process:" + event, function(data) {
                            if (data.id === id) cb(data.line);
                        }));
                    }

                    line("stdout", h.onStdout);
                    line("stderr", h.onStderr);

                    var unsubExit = on("process:exit", function(data) {
                        if (data.id !== id) return;
                        for (var i = 0; i < unsubs.length; i++) unsubs[i]();
                        unsubExit();
                        if (typeof h.onExit === "function") h.onExit(data.code);
                    });

                    return {
                        id: id,
                        kill: function() {
                            return invoke("vesper:process:kill", { id: id });
                        }
                    };
                });
        },
        /**
         * Terminate a spawned process by id (escalates to a hard kill).
         * @param {number} id
         * @returns {Promise<boolean>} False for an unknown or finished id.
         */
        kill: function(id) {
            return invoke("vesper:process:kill", { id: id });
        },
    };

    var update = {
        /**
         * Check the configured manifest for a newer version.
         * @returns {Promise<{version:string, notes:string, download_url:string}|null>}
         */
        check: function() {
            return invoke("vesper:update:check", {});
        },
        /**
         * Download an update binary. Calls onProgress(percent) during the transfer.
         * @param {string} url - Direct download URL from check() result.
         * @param {function(number):void} [onProgress]
         * @returns {Promise<string>} Local path to the downloaded binary.
         */
        download: function(url, onProgress) {
            var unsub;
            if (typeof onProgress === "function") {
                unsub = on("update:progress", function(data) {
                    onProgress(data.percent);
                });
            }
            return invoke("vesper:update:download", { url: url }).then(
                function(result) {
                    if (unsub) unsub();
                    return result;
                },
                function(err) {
                    if (unsub) unsub();
                    throw err;
                }
            );
        },
        /**
         * Install the binary at path and restart the app.
         * @param {string} path - Local path returned by download().
         * @param {string} [sha256] - Expected SHA-256 hex digest from the manifest.
         * @returns {Promise<void>}
         */
        install: function(path, sha256) {
            return invoke("vesper:update:install", { path: path, sha256: sha256 || "" });
        },
    };

    global.vesper = {
        invoke,
        on,
        quit,
        capabilities,
        window: window_controls,
        screen,
        os,
        drop,
        dialog,
        notify,
        fs,
        autostart,
        power,
        security,
        badge,
        shell,
        clipboard,
        net,
        process: processNs,
        update,
    };
})(window);
