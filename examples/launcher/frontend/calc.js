// A calculator that never calls eval() or new Function().
//
// User input is a string from a text box; running it through eval would hand the
// page's full authority to whatever was typed. Instead this tokenises the
// expression and evaluates it with the shunting-yard algorithm — it only ever
// does arithmetic, so the worst a hostile string can do is throw.
//
// Supports: + - * / % ^, unary minus, parentheses, decimals, and the constants
// pi and e. Exposed as window.Calc.evaluate(expr) -> number (throws on bad input).

(function (global) {
    var OPERATORS = {
        "+": { prec: 2, assoc: "L", fn: function (a, b) { return a + b; } },
        "-": { prec: 2, assoc: "L", fn: function (a, b) { return a - b; } },
        "*": { prec: 3, assoc: "L", fn: function (a, b) { return a * b; } },
        "/": { prec: 3, assoc: "L", fn: function (a, b) {
            if (b === 0) throw new Error("Division by zero");
            return a / b;
        } },
        "%": { prec: 3, assoc: "L", fn: function (a, b) { return a % b; } },
        "^": { prec: 4, assoc: "R", fn: function (a, b) { return Math.pow(a, b); } },
    };

    var CONSTANTS = { pi: Math.PI, e: Math.E };

    function tokenize(expr) {
        var tokens = [];
        var i = 0;
        while (i < expr.length) {
            var ch = expr[i];

            if (ch === " " || ch === "\t") { i++; continue; }

            // Number: digits with an optional single decimal point.
            if ((ch >= "0" && ch <= "9") || ch === ".") {
                var num = "";
                var seenDot = false;
                while (i < expr.length) {
                    var c = expr[i];
                    if (c >= "0" && c <= "9") { num += c; i++; }
                    else if (c === "." && !seenDot) { seenDot = true; num += c; i++; }
                    else break;
                }
                if (num === "." ) throw new Error("Stray '.'");
                tokens.push({ type: "num", value: parseFloat(num) });
                continue;
            }

            // Named constant (pi, e).
            if ((ch >= "a" && ch <= "z") || (ch >= "A" && ch <= "Z")) {
                var name = "";
                while (i < expr.length && /[a-zA-Z]/.test(expr[i])) { name += expr[i]; i++; }
                var key = name.toLowerCase();
                if (!(key in CONSTANTS)) throw new Error("Unknown name: " + name);
                tokens.push({ type: "num", value: CONSTANTS[key] });
                continue;
            }

            if (ch === "(" || ch === ")") {
                tokens.push({ type: ch === "(" ? "lparen" : "rparen" });
                i++;
                continue;
            }

            if (ch in OPERATORS) {
                tokens.push({ type: "op", value: ch });
                i++;
                continue;
            }

            throw new Error("Unexpected character: " + ch);
        }
        return tokens;
    }

    // Rewrite leading/after-operator "-" as a unary negation marker so the
    // shunting yard can treat it as a right-associative high-precedence op.
    function markUnary(tokens) {
        var out = [];
        for (var i = 0; i < tokens.length; i++) {
            var t = tokens[i];
            if (t.type === "op" && t.value === "-") {
                var prev = out[out.length - 1];
                var isUnary = !prev || prev.type === "op" || prev.type === "lparen";
                if (isUnary) { out.push({ type: "op", value: "neg" }); continue; }
            }
            out.push(t);
        }
        return out;
    }

    var NEG = { prec: 5, assoc: "R" };

    function toRPN(tokens) {
        var output = [];
        var stack = [];
        for (var i = 0; i < tokens.length; i++) {
            var t = tokens[i];
            if (t.type === "num") {
                output.push(t);
            } else if (t.type === "op") {
                var o1 = t.value === "neg" ? NEG : OPERATORS[t.value];
                while (stack.length) {
                    var top = stack[stack.length - 1];
                    if (top.type !== "op") break;
                    var o2 = top.value === "neg" ? NEG : OPERATORS[top.value];
                    if ((o1.assoc === "L" && o1.prec <= o2.prec) ||
                        (o1.assoc === "R" && o1.prec < o2.prec)) {
                        output.push(stack.pop());
                    } else break;
                }
                stack.push(t);
            } else if (t.type === "lparen") {
                stack.push(t);
            } else if (t.type === "rparen") {
                var found = false;
                while (stack.length) {
                    var s = stack.pop();
                    if (s.type === "lparen") { found = true; break; }
                    output.push(s);
                }
                if (!found) throw new Error("Mismatched parenthesis");
            }
        }
        while (stack.length) {
            var r = stack.pop();
            if (r.type === "lparen" || r.type === "rparen") {
                throw new Error("Mismatched parenthesis");
            }
            output.push(r);
        }
        return output;
    }

    function evalRPN(rpn) {
        var st = [];
        for (var i = 0; i < rpn.length; i++) {
            var t = rpn[i];
            if (t.type === "num") {
                st.push(t.value);
            } else if (t.value === "neg") {
                if (st.length < 1) throw new Error("Malformed expression");
                st.push(-st.pop());
            } else {
                if (st.length < 2) throw new Error("Malformed expression");
                var b = st.pop();
                var a = st.pop();
                st.push(OPERATORS[t.value].fn(a, b));
            }
        }
        if (st.length !== 1) throw new Error("Malformed expression");
        var result = st[0];
        if (!isFinite(result)) throw new Error("Result is not finite");
        return result;
    }

    function evaluate(expr) {
        if (typeof expr !== "string" || expr.trim() === "") {
            throw new Error("Empty expression");
        }
        return evalRPN(toRPN(markUnary(tokenize(expr))));
    }

    // Cheap pre-check for the command palette: does this look like maths rather
    // than a command name? Only characters the tokenizer understands, and at
    // least one digit or a constant.
    function looksNumeric(expr) {
        if (!/[0-9]/.test(expr) && !/\b(pi|e)\b/i.test(expr)) return false;
        return /^[\s0-9.+\-*/%^()piePIE]+$/.test(expr) && /[-+*/%^]/.test(expr);
    }

    global.Calc = { evaluate: evaluate, looksNumeric: looksNumeric };
})(window);
