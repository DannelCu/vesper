(function () {
    if (!window.vesper) return;

    window.vesper.theme = {
        /**
         * Get the current OS theme.
         * @returns {Promise<{theme: "Light"|"Dark", is_dark: boolean}>}
         */
        get: function () {
            return window.vesper.invoke("vesper:theme:get", {});
        },
        /**
         * Subscribe to OS theme changes.
         * Callback receives { theme, is_dark } whenever the user switches modes.
         * @param {function({theme: string, is_dark: boolean}): void} callback
         * @returns {function(): void} Unsubscribe function.
         */
        onChange: function (callback) {
            return window.vesper.on("theme:change", callback);
        },
    };
})();
