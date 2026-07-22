(function () {
    if (!window.vesper) return;

    var reporting = false;

    function report(message, stack, kind) {
        // A reporting failure must never cascade into more reports.
        if (reporting) return;
        reporting = true;
        window.vesper.invoke("vesper:crash:report", {
            message: String(message || "Unknown error"),
            stack: String(stack || ""),
            kind: kind
        }).catch(function () {}).then(function () { reporting = false; });
    }

    window.addEventListener("error", function (event) {
        var stack = event.error && event.error.stack ? event.error.stack : "";
        report(event.message, stack, "error");
    });

    window.addEventListener("unhandledrejection", function (event) {
        var reason = event.reason || {};
        report(reason.message || reason, reason.stack || "", "unhandledrejection");
    });

    window.vesper.crash = {
        /**
         * Report an error to the backend crash reporter manually.
         * A no-op (resolves false) when the app has no DSN configured.
         * @param {Error|string} error
         * @returns {Promise<boolean>}
         */
        report: function (error) {
            var message = error && error.message ? error.message : String(error);
            var stack = error && error.stack ? error.stack : "";
            return window.vesper.invoke("vesper:crash:report", {
                message: message,
                stack: stack,
                kind: "manual"
            });
        }
    };
})();
