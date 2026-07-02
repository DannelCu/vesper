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
        shell,
        clipboard,
        update,
    };
})(window);
