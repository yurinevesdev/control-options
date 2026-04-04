/**
 * Eagle System — Database Layer (IndexedDB)
 * Gerencia persistência local de estruturas e pernas
 */

'use strict';

const DB = (() => {
    const DB_NAME = 'eagle_opcoes_v2';
    const DB_VERSION = 2;
    let _db = null;

    function open() {
        return new Promise((resolve, reject) => {
            const req = indexedDB.open(DB_NAME, DB_VERSION);

            req.onupgradeneeded = e => {
                const db = e.target.result;

                // Estruturas
                if (!db.objectStoreNames.contains('estruturas')) {
                    const es = db.createObjectStore('estruturas', { keyPath: 'id', autoIncrement: true });
                    es.createIndex('criadoEm', 'criadoEm', { unique: false });
                }

                // Pernas
                if (!db.objectStoreNames.contains('legs')) {
                    const ls = db.createObjectStore('legs', { keyPath: 'id', autoIncrement: true });
                    ls.createIndex('estruturaId', 'estruturaId', { unique: false });
                }
            };

            req.onsuccess = e => {
                _db = e.target.result;
                resolve(_db);
            };

            req.onerror = () => reject(req.error);
        });
    }

    function _tx(store, mode = 'readonly') {
        return _db.transaction(store, mode).objectStore(store);
    }

    function getAll(store) {
        return new Promise((res, rej) => {
            const req = _tx(store).getAll();
            req.onsuccess = () => res(req.result);
            req.onerror = () => rej(req.error);
        });
    }

    function get(store, key) {
        return new Promise((res, rej) => {
            const req = _tx(store).get(key);
            req.onsuccess = () => res(req.result);
            req.onerror = () => rej(req.error);
        });
    }

    function put(store, obj) {
        return new Promise((res, rej) => {
            const req = _tx(store, 'readwrite').put(obj);
            req.onsuccess = () => res(req.result);
            req.onerror = () => rej(req.error);
        });
    }

    function del(store, key) {
        return new Promise((res, rej) => {
            const req = _tx(store, 'readwrite').delete(key);
            req.onsuccess = () => res();
            req.onerror = () => rej(req.error);
        });
    }

    function getByIndex(store, indexName, value) {
        return new Promise((res, rej) => {
            const req = _tx(store).index(indexName).getAll(value);
            req.onsuccess = () => res(req.result);
            req.onerror = () => rej(req.error);
        });
    }

    // Salva estrutura (insert ou update)
    async function saveEstrutura(obj) {
        if (!obj.criadoEm) obj.criadoEm = new Date().toISOString();
        obj.atualizadoEm = new Date().toISOString();
        return await put('estruturas', obj);
    }

    // Salva perna
    async function saveLeg(obj) {
        return await put('legs', obj);
    }

    // Deleta estrutura e todas as suas pernas
    async function deleteEstrutura(id) {
        const legs = await getByIndex('legs', 'estruturaId', id);
        for (const leg of legs) await del('legs', leg.id);
        await del('estruturas', id);
    }

    // Busca todas as estruturas com contagem de pernas
    async function getEstruturas() {
        const ests = await getAll('estruturas');
        const legs = await getAll('legs');
        return ests.map(e => ({
            ...e,
            _legsCount: legs.filter(l => l.estruturaId === e.id).length
        })).sort((a, b) => b.id - a.id);
    }

    // Busca pernas de uma estrutura
    async function getLegs(estruturaId) {
        return await getByIndex('legs', 'estruturaId', estruturaId);
    }

    return { open, saveEstrutura, saveLeg, del: del.bind(null), getEstruturas, getLegs, get, getAll, deleteEstrutura };
})();