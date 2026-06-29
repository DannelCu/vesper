(function () {
  "use strict";

  if (!window.vesper) {
    console.error("vesper-mongodb: window.vesper not found. Load vesper.js first.");
    return;
  }

  window.vesper.mongo = {
    /**
     * Find all documents in a collection matching a filter.
     * @param {string} collection
     * @param {object} [filter={}]
     * @param {number} [limit=0]  0 = no limit
     * @returns {Promise<object[]>}
     */
    find: function (collection, filter, limit) {
      return window.vesper.invoke("mongo:find", {
        collection: collection,
        filter: filter || {},
        limit: limit || 0,
      });
    },

    /**
     * Find the first document matching a filter.
     * @param {string} collection
     * @param {object} [filter={}]
     * @returns {Promise<object|null>}
     */
    findOne: function (collection, filter) {
      return window.vesper.invoke("mongo:find_one", {
        collection: collection,
        filter: filter || {},
      });
    },

    /**
     * Insert a single document.
     * @param {string} collection
     * @param {object} document
     * @returns {Promise<{id: string}>}
     */
    insertOne: function (collection, document) {
      return window.vesper.invoke("mongo:insert_one", {
        collection: collection,
        document: document,
      });
    },

    /**
     * Insert multiple documents.
     * @param {string} collection
     * @param {object[]} documents
     * @returns {Promise<{ids: string[]}>}
     */
    insertMany: function (collection, documents) {
      return window.vesper.invoke("mongo:insert_many", {
        collection: collection,
        documents: documents,
      });
    },

    /**
     * Update the first document matching a filter.
     * @param {string} collection
     * @param {object} filter
     * @param {object} update  e.g. { $set: { field: value } }
     * @returns {Promise<{matched: number, modified: number}>}
     */
    updateOne: function (collection, filter, update) {
      return window.vesper.invoke("mongo:update_one", {
        collection: collection,
        filter: filter,
        update: update,
      });
    },

    /**
     * Update all documents matching a filter.
     * @param {string} collection
     * @param {object} filter
     * @param {object} update
     * @returns {Promise<{matched: number, modified: number}>}
     */
    updateMany: function (collection, filter, update) {
      return window.vesper.invoke("mongo:update_many", {
        collection: collection,
        filter: filter,
        update: update,
      });
    },

    /**
     * Delete the first document matching a filter.
     * @param {string} collection
     * @param {object} filter
     * @returns {Promise<{deleted: number}>}
     */
    deleteOne: function (collection, filter) {
      return window.vesper.invoke("mongo:delete_one", {
        collection: collection,
        filter: filter,
      });
    },

    /**
     * Delete all documents matching a filter.
     * @param {string} collection
     * @param {object} filter
     * @returns {Promise<{deleted: number}>}
     */
    deleteMany: function (collection, filter) {
      return window.vesper.invoke("mongo:delete_many", {
        collection: collection,
        filter: filter,
      });
    },

    /**
     * Count documents matching a filter.
     * @param {string} collection
     * @param {object} [filter={}]
     * @returns {Promise<number>}
     */
    count: function (collection, filter) {
      return window.vesper.invoke("mongo:count", {
        collection: collection,
        filter: filter || {},
      });
    },
  };
})();
