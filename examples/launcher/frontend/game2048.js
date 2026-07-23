// 2048 — the classic 4x4 slide-and-merge game.
//
// Self-contained: create(container, opts) mounts a board into `container` and
// returns a controller with .move(dir), .restart(), .destroy(), and .focusable.
// It owns none of the app's chrome — app.js decides when it is visible, feeds it
// arrow keys, and persists the best score. opts.onScore(score, best) fires after
// every move so the host can update its own labels and store the best.

(function (global) {
    var SIZE = 4;

    function emptyGrid() {
        var g = [];
        for (var r = 0; r < SIZE; r++) {
            g.push([0, 0, 0, 0]);
        }
        return g;
    }

    function create(container, opts) {
        opts = opts || {};
        var onScore = opts.onScore || function () {};
        var best = opts.best || 0;

        var grid = emptyGrid();
        var score = 0;
        var won = false;
        var over = false;

        var boardEl = document.createElement("div");
        boardEl.className = "g2048-board";
        container.innerHTML = "";
        container.appendChild(boardEl);

        var cells = [];
        for (var i = 0; i < SIZE * SIZE; i++) {
            var cell = document.createElement("div");
            cell.className = "g2048-cell";
            boardEl.appendChild(cell);
            cells.push(cell);
        }

        var statusEl = document.createElement("div");
        statusEl.className = "g2048-status";
        container.appendChild(statusEl);

        function addRandom() {
            var free = [];
            for (var r = 0; r < SIZE; r++) {
                for (var c = 0; c < SIZE; c++) {
                    if (grid[r][c] === 0) free.push([r, c]);
                }
            }
            if (!free.length) return;
            var spot = free[Math.floor(Math.random() * free.length)];
            grid[spot[0]][spot[1]] = Math.random() < 0.9 ? 2 : 4;
        }

        function render() {
            for (var r = 0; r < SIZE; r++) {
                for (var c = 0; c < SIZE; c++) {
                    var v = grid[r][c];
                    var el = cells[r * SIZE + c];
                    el.textContent = v === 0 ? "" : String(v);
                    el.className = "g2048-cell" + (v ? " v" + (v > 2048 ? "super" : v) : "");
                }
            }
            if (won && !over) {
                statusEl.textContent = "You reached 2048! Keep going or press New game.";
            } else if (over) {
                statusEl.textContent = "No moves left — press New game.";
            } else {
                statusEl.textContent = "";
            }
            if (best < score) best = score;
            onScore(score, best);
        }

        // Slide one row to the left, merging equal neighbours once each.
        // Returns { row, gained, moved }.
        function slideRow(row) {
            var nums = row.filter(function (n) { return n !== 0; });
            var out = [];
            var gained = 0;
            for (var i = 0; i < nums.length; i++) {
                if (i + 1 < nums.length && nums[i] === nums[i + 1]) {
                    var merged = nums[i] * 2;
                    out.push(merged);
                    gained += merged;
                    if (merged === 2048) won = true;
                    i++;
                } else {
                    out.push(nums[i]);
                }
            }
            while (out.length < SIZE) out.push(0);
            var moved = false;
            for (var j = 0; j < SIZE; j++) {
                if (out[j] !== row[j]) { moved = true; break; }
            }
            return { row: out, gained: gained, moved: moved };
        }

        function rotate(g) {
            // Rotate the grid clockwise so every direction reduces to "left".
            var out = emptyGrid();
            for (var r = 0; r < SIZE; r++) {
                for (var c = 0; c < SIZE; c++) {
                    out[c][SIZE - 1 - r] = g[r][c];
                }
            }
            return out;
        }

        function rotateN(g, times) {
            for (var i = 0; i < times; i++) g = rotate(g);
            return g;
        }

        var TURNS = { left: 0, up: 3, right: 2, down: 1 };

        function move(dir) {
            if (over) return;
            var turns = TURNS[dir];
            if (turns === undefined) return;

            // Rotate so the move is a leftward slide, slide, rotate back.
            var work = rotateN(grid, turns);
            var movedAny = false;
            for (var r = 0; r < SIZE; r++) {
                var res = slideRow(work[r]);
                work[r] = res.row;
                score += res.gained;
                if (res.moved) movedAny = true;
            }
            grid = rotateN(work, (4 - turns) % 4);

            if (movedAny) {
                addRandom();
                if (!hasMoves()) over = true;
            }
            render();
        }

        function hasMoves() {
            for (var r = 0; r < SIZE; r++) {
                for (var c = 0; c < SIZE; c++) {
                    if (grid[r][c] === 0) return true;
                    if (c + 1 < SIZE && grid[r][c] === grid[r][c + 1]) return true;
                    if (r + 1 < SIZE && grid[r][c] === grid[r + 1][c]) return true;
                }
            }
            return false;
        }

        function restart() {
            grid = emptyGrid();
            score = 0;
            won = false;
            over = false;
            addRandom();
            addRandom();
            render();
        }

        restart();

        return {
            move: move,
            restart: restart,
            destroy: function () { container.innerHTML = ""; },
        };
    }

    global.Game2048 = { create: create };
})(window);
