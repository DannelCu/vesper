(function () {
  "use strict";

  if (!window.vesper) {
    console.error("vesper-keychain: window.vesper not found. Load vesper.js first.");
    return;
  }

  window.vesper.keychain = {
    /**
     * Retrieve a value from the OS keychain.
     * @param {string} key
     * @returns {Promise<string|null>}
     */
    get: function (key) {
      return window.vesper.invoke("keychain:get", { key: key });
    },

    /**
     * Store a value in the OS keychain.
     * @param {string} key
     * @param {string} value
     * @returns {Promise<void>}
     */
    set: function (key, value) {
      return window.vesper.invoke("keychain:set", { key: key, value: value });
    },

    /**
     * Delete a value from the OS keychain. No-op if key does not exist.
     * @param {string} key
     * @returns {Promise<void>}
     */
    delete: function (key) {
      return window.vesper.invoke("keychain:delete", { key: key });
    },

    /**
     * Check whether a key exists in the OS keychain.
     * @param {string} key
     * @returns {Promise<boolean>}
     */
    has: function (key) {
      return window.vesper.invoke("keychain:has", { key: key });
    },
  };
})();
