(function () {
    if (!window.vesper) return;

    window.vesper.shortcuts = {
        /**
         * Register a global shortcut. When triggered, fires a "shortcut" event
         * on the frontend with { accelerator }.
         * @param {string} accelerator - e.g. "ctrl+shift+s"
         * @returns {Promise<void>}
         */
        register: function (accelerator) {
            return window.vesper.invoke("vesper:shortcuts:register", { accelerator: accelerator });
        },
        /**
         * Unregister a previously registered shortcut.
         * @param {string} accelerator
         * @returns {Promise<void>}
         */
        unregister: function (accelerator) {
            return window.vesper.invoke("vesper:shortcuts:unregister", { accelerator: accelerator });
        },
        /**
         * Unregister all shortcuts registered via IPC.
         * @returns {Promise<void>}
         */
        unregisterAll: function () {
            return window.vesper.invoke("vesper:shortcuts:unregister_all", {});
        },
    };
})();
