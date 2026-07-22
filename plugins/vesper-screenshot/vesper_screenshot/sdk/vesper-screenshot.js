(function () {
    if (!window.vesper) return;

    window.vesper.screenshot = {
        /**
         * Capture the screen as a PNG data URL (usable directly as <img src>).
         *
         * Rejects with an explanatory message under Wayland and when macOS
         * lacks the Screen Recording permission — check the `screenshot`
         * capability first: (await vesper.capabilities()).screenshot
         *
         * @param {object} [options]
         * @param {number} [options.monitor=0] - 0 = whole virtual screen,
         *        1..N = individual monitors.
         * @param {{left:number, top:number, width:number, height:number}}
         *        [options.region] - Overrides monitor.
         * @returns {Promise<string>} data:image/png;base64,... URL.
         */
        capture: function (options) {
            var opts = options || {};
            return window.vesper.invoke("vesper:screenshot:capture", {
                monitor: opts.monitor || 0,
                region: opts.region || null,
                dest: ""
            });
        },
        /**
         * Capture straight to a file (path validated by the app's fs scope).
         * @param {string} dest - Destination .png path.
         * @param {object} [options] - Same monitor/region options as capture().
         * @returns {Promise<string>} The written path.
         */
        captureToFile: function (dest, options) {
            var opts = options || {};
            return window.vesper.invoke("vesper:screenshot:capture", {
                monitor: opts.monitor || 0,
                region: opts.region || null,
                dest: dest
            });
        },
        /**
         * Monitor geometry as the capture backend sees it.
         * Index 0 is the whole virtual screen.
         * @returns {Promise<object[]>}
         */
        monitors: function () {
            return window.vesper.invoke("vesper:screenshot:monitors", {});
        }
    };
})();
