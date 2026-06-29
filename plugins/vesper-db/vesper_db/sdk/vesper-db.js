(function () {
  "use strict";

  if (!window.vesper) {
    console.error("vesper-db: window.vesper not found. Load vesper.js first.");
    return;
  }

  window.vesper.db = {
    /**
     * Run a SELECT query and return rows as an array of objects.
     * @param {string} sql   SQL with ? placeholders
     * @param {Array}  params  Positional parameter values
     * @returns {Promise<Array<Object>>}
     */
    query: function (sql, params) {
      return window.vesper.invoke("db:query", { sql: sql, params: params || [] });
    },

    /**
     * Run an INSERT / UPDATE / DELETE statement.
     * @param {string} sql
     * @param {Array}  params
     * @returns {Promise<{affected: number}>}
     */
    execute: function (sql, params) {
      return window.vesper.invoke("db:execute", { sql: sql, params: params || [] });
    },

    /**
     * Run multiple statements as a single atomic transaction.
     * @param {Array<{sql: string, params?: Array}>} statements
     * @returns {Promise<{affected: number}>}
     */
    transaction: function (statements) {
      return window.vesper.invoke("db:transaction", { statements: statements });
    },
  };
})();
