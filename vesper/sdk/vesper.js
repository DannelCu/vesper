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
    };

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
        update,
    };
})(window);
