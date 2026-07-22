(function () {
    if (!window.vesper) return;

    window.vesper.notifyRich = {
        /**
         * Show a rich notification with click/action callbacks.
         *
         * The core vesper.notify(title, body) keeps working without this
         * plugin; this adds knowing that the user responded.
         *
         * @param {string} title
         * @param {object} [options]
         * @param {string} [options.body]
         * @param {string[]} [options.buttons] - Action button labels.
         * @param {string} [options.icon] - Path to an icon image.
         * @param {boolean} [options.sound=false] - Default notification sound.
         * @param {function():void} [options.onClick] - Body clicked.
         * @param {function(string):void} [options.onAction] - Button label pressed.
         * @returns {Promise<string>} Notification id.
         */
        send: function (title, options) {
            var opts = options || {};
            return window.vesper.invoke("vesper:notify:send", {
                title: title,
                body: opts.body || "",
                buttons: opts.buttons || [],
                icon: opts.icon || "",
                sound: !!opts.sound
            }).then(function (id) {
                var unsubs = [];

                function cleanup() {
                    for (var i = 0; i < unsubs.length; i++) unsubs[i]();
                    unsubs = [];
                }

                if (typeof opts.onClick === "function") {
                    unsubs.push(window.vesper.on("notify:clicked", function (data) {
                        if (data.id === id) { opts.onClick(); cleanup(); }
                    }));
                }
                if (typeof opts.onAction === "function") {
                    unsubs.push(window.vesper.on("notify:action", function (data) {
                        if (data.id === id) { opts.onAction(data.button); cleanup(); }
                    }));
                }
                return id;
            });
        },
        /**
         * Subscribe to clicks on any notification sent by this plugin.
         * @param {function({id:string}):void} callback
         * @returns {function():void} Unsubscribe.
         */
        onClicked: function (callback) {
            return window.vesper.on("notify:clicked", callback);
        },
        /**
         * Subscribe to action-button presses on any notification.
         * @param {function({id:string, button:string}):void} callback
         * @returns {function():void} Unsubscribe.
         */
        onAction: function (callback) {
            return window.vesper.on("notify:action", callback);
        }
    };
})();
