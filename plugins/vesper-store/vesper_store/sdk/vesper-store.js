(function () {
    if (!window.vesper) {
        console.error("vesper-store: vesper.js must be loaded before vesper-store.js");
        return;
    }

    window.vesper.store = {
        /**
         * Get a value from the store.
         * @param {string} key
         * @returns {Promise<any>}
         */
        get: function (key) {
            return window.vesper.invoke("store:get", { key: key });
        },
        /**
         * Set a value in the store.
         * @param {string} key
         * @param {any} value
         * @returns {Promise<void>}
         */
        set: function (key, value) {
            return window.vesper.invoke("store:set", { key: key, value: value });
        },
        /**
         * Delete a key from the store.
         * @param {string} key
         * @returns {Promise<void>}
         */
        delete: function (key) {
            return window.vesper.invoke("store:delete", { key: key });
        },
        /**
         * Return true if the key exists in the store.
         * @param {string} key
         * @returns {Promise<boolean>}
         */
        has: function (key) {
            return window.vesper.invoke("store:has", { key: key });
        },
        /**
         * Remove all keys from the store.
         * @returns {Promise<void>}
         */
        clear: function () {
            return window.vesper.invoke("store:clear", {});
        },
        /**
         * Return all keys in the store.
         * @returns {Promise<string[]>}
         */
        keys: function () {
            return window.vesper.invoke("store:keys", {});
        },
    };
})();
