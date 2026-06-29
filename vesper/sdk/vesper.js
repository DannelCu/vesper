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
         * @returns {Promise<void>}
         */
        install: function(path) {
            return invoke("vesper:update:install", { path: path });
        },
    };

    global.vesper = {
        invoke,
        on,
        dialog,
        notify,
        fs,
        update,
    };
})(window);
