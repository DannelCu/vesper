(function () {
  "use strict";

  if (!window.vesper) {
    console.error("vesper-http: window.vesper not found. Load vesper.js first.");
    return;
  }

  window.vesper.http = {
    /**
     * HTTP GET — returns {status, ok, headers, body, json}.
     * @param {string} url
     * @param {{params?: object, headers?: object, timeout?: number}} [options]
     */
    get: function (url, options) {
      return window.vesper.invoke("http:get", { url: url, ...(options || {}) });
    },

    /**
     * HTTP POST.
     * @param {string} url
     * @param {{json?: object, data?: object, headers?: object, timeout?: number}} [options]
     */
    post: function (url, options) {
      return window.vesper.invoke("http:post", { url: url, ...(options || {}) });
    },

    /**
     * HTTP PUT.
     * @param {string} url
     * @param {{json?: object, data?: object, headers?: object, timeout?: number}} [options]
     */
    put: function (url, options) {
      return window.vesper.invoke("http:put", { url: url, ...(options || {}) });
    },

    /**
     * HTTP PATCH.
     * @param {string} url
     * @param {{json?: object, data?: object, headers?: object, timeout?: number}} [options]
     */
    patch: function (url, options) {
      return window.vesper.invoke("http:patch", { url: url, ...(options || {}) });
    },

    /**
     * HTTP DELETE.
     * @param {string} url
     * @param {{params?: object, headers?: object, timeout?: number}} [options]
     */
    delete: function (url, options) {
      return window.vesper.invoke("http:delete", { url: url, ...(options || {}) });
    },
  };
})();
