(function () {
    if (!window.vesper) return;

    window.vesper.serial = {
        /**
         * List connected serial devices.
         * @returns {Promise<{device:string, description:string, hwid:string}[]>}
         */
        listPorts: function () {
            return window.vesper.invoke("vesper:serial:list_ports", {});
        },
        /**
         * Open a serial port and stream incoming data.
         *
         * @param {string} port - "COM3", "/dev/ttyUSB0", or a pyserial URL
         *        like "loop://".
         * @param {object} [options]
         * @param {number} [options.baudrate=9600]
         * @param {function(string):void} [options.onData] - Incoming text
         *        (undecodable bytes replaced).
         * @param {function():void} [options.onClose] - Port closed, including
         *        a device unplugged mid-session.
         * @returns {Promise<{id:number, write:function(string):Promise<number>,
         *          close:function():Promise<boolean>}>}
         */
        open: function (port, options) {
            var opts = options || {};
            return window.vesper.invoke("vesper:serial:open", {
                port: port,
                baudrate: opts.baudrate || 9600
            }).then(function (id) {
                var unsubs = [];

                if (typeof opts.onData === "function") {
                    unsubs.push(window.vesper.on("serial:data", function (event) {
                        if (event.id === id) opts.onData(event.data);
                    }));
                }
                unsubs.push(window.vesper.on("serial:closed", function (event) {
                    if (event.id !== id) return;
                    for (var i = 0; i < unsubs.length; i++) unsubs[i]();
                    if (typeof opts.onClose === "function") opts.onClose();
                }));

                return {
                    id: id,
                    write: function (data) {
                        return window.vesper.invoke("vesper:serial:write", { id: id, data: data });
                    },
                    close: function () {
                        return window.vesper.invoke("vesper:serial:close", { id: id });
                    }
                };
            });
        },
        /**
         * Write to an open port by id.
         * @param {number} id
         * @param {string} data
         * @returns {Promise<number>} Bytes written.
         */
        write: function (id, data) {
            return window.vesper.invoke("vesper:serial:write", { id: id, data: data });
        },
        /**
         * Close a port by id.
         * @param {number} id
         * @returns {Promise<boolean>}
         */
        close: function (id) {
            return window.vesper.invoke("vesper:serial:close", { id: id });
        }
    };
})();
