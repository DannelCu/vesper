(function () {
    if (!window.vesper) return;

    window.vesper.sysinfo = {
        /**
         * One reading of CPU, memory, disks, network, battery and uptime.
         * @returns {Promise<{cpu:{percent:number,count:number},
         *          memory:{total:number,available:number,percent:number},
         *          disks:object[], net:{bytes_sent:number,bytes_recv:number},
         *          battery:{percent:number,plugged:boolean}|null,
         *          uptime:number}>}
         */
        snapshot: function () {
            return window.vesper.invoke("vesper:sysinfo:snapshot", {});
        },
        /**
         * Stream readings as vesper:sysinfo:tick events.
         *
         * One stream per app: subscribing again retunes the interval. The
         * stream stops cleanly when the app closes.
         *
         * @param {object} [options]
         * @param {number} [options.interval=2] - Seconds between ticks.
         * @param {function(object):void} [options.onTick]
         * @returns {Promise<{unsubscribe:function():Promise<boolean>}>}
         */
        subscribe: function (options) {
            var opts = options || {};
            var unsub;
            if (typeof opts.onTick === "function") {
                unsub = window.vesper.on("sysinfo:tick", opts.onTick);
            }
            return window.vesper.invoke("vesper:sysinfo:subscribe", {
                interval: opts.interval || 2
            }).then(function () {
                return {
                    unsubscribe: function () {
                        if (unsub) unsub();
                        return window.vesper.invoke("vesper:sysinfo:unsubscribe", {});
                    }
                };
            });
        },
        /**
         * Stop the tick stream.
         * @returns {Promise<boolean>} False when none was running.
         */
        unsubscribe: function () {
            return window.vesper.invoke("vesper:sysinfo:unsubscribe", {});
        },
        /**
         * Subscribe to tick events only (stream must be started elsewhere).
         * @param {function(object):void} callback
         * @returns {function():void} Unsubscribe function.
         */
        onTick: function (callback) {
            return window.vesper.on("sysinfo:tick", callback);
        }
    };
})();
