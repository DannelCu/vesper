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

    global.vesper = {
        invoke,
        on,
        dialog,
        notify,
    };
})(window);
