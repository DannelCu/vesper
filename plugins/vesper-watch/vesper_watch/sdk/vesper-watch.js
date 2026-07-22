(function () {
    if (!window.vesper) return;

    window.vesper.watch = {
        /**
         * Watch a path for filesystem changes.
         *
         * The path must be inside the app's fs scope. Events arrive as
         * { id, kind, path, dest_path?, is_dir } with kind one of
         * created | modified | deleted | moved.
         *
         * @param {string} path
         * @param {object} [options]
         * @param {boolean} [options.recursive=true]
         * @param {number} [options.debounce] - Seconds; repeats of the same
         *        (kind, path) within the window are dropped.
         * @param {function(object):void} [options.onChange] - Called per event
         *        for this watch only.
         * @returns {Promise<{id:number, unwatch:function():Promise<boolean>}>}
         */
        watch: function (path, options) {
            var opts = options || {};
            return window.vesper.invoke("vesper:fs:watch", {
                path: path,
                recursive: opts.recursive === undefined ? true : !!opts.recursive,
                debounce: opts.debounce === undefined ? -1 : opts.debounce
            }).then(function (id) {
                var unsub;
                if (typeof opts.onChange === "function") {
                    unsub = window.vesper.on("fs:changed", function (event) {
                        if (event.id === id) opts.onChange(event);
                    });
                }
                return {
                    id: id,
                    unwatch: function () {
                        if (unsub) unsub();
                        return window.vesper.invoke("vesper:fs:unwatch", { id: id });
                    }
                };
            });
        },
        /**
         * Stop a watch by id.
         * @param {number} id
         * @returns {Promise<boolean>} False for an unknown id.
         */
        unwatch: function (id) {
            return window.vesper.invoke("vesper:fs:unwatch", { id: id });
        },
        /**
         * Subscribe to every fs change event, across all watches.
         * @param {function(object):void} callback
         * @returns {function():void} Unsubscribe function.
         */
        onChange: function (callback) {
            return window.vesper.on("fs:changed", callback);
        }
    };
})();
