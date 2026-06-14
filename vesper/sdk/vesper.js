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

    global.vesper = {
        invoke
    };
})(window);
