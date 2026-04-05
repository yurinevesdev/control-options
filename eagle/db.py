"""
Camada de persistência SQLite — equivalente lógico a js/db.js (eagle_opcoes_v2).
Colunas em snake_case no SQL; dicts expostos com chaves camelCase como no JS.

Melhorias aplicadas:
- Índices em colunas frequentemente consultadas
- Método de backup
- Validação de schema
"""

from __future__ import annotations

import sqlite3
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from eagle.logger import get_logger

log = get_logger("db")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _row_estrutura(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "nome": row["nome"],
        "ativo": row["ativo"],
        "tipo": row["tipo"],
        "precoAtual": row["preco_atual"],
        "dataVenc": row["data_venc"],
        "obs": row["obs"],
        "criadoEm": row["criado_em"],
        "atualizadoEm": row["atualizado_em"],
    }


def _row_leg(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "estruturaId": row["estrutura_id"],
        "operacao": row["operacao"],
        "tipo": row["tipo"],
        "qtd": row["qtd"],
        "strike": row["strike"],
        "ticker": row["ticker"],
        "vencimento": row["vencimento"],
        "premio": row["premio"],
        "iv": row["iv"],
        "delta": row["delta"],
        "gamma": row["gamma"],
        "theta": row["theta"],
        "vega": row["vega"],
    }


class Database:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA journal_mode = WAL")  # Melhor performance
            self._init_schema()
        return self._conn

    def _init_schema(self) -> None:
        c = self._conn
        assert c is not None
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS estruturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                ativo TEXT,
                tipo TEXT,
                preco_atual REAL,
                data_venc TEXT,
                obs TEXT,
                criado_em TEXT,
                atualizado_em TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_est_criado ON estruturas(criado_em);
            CREATE INDEX IF NOT EXISTS idx_est_tipo ON estruturas(tipo);
            CREATE INDEX IF NOT EXISTS idx_est_ativo ON estruturas(ativo);
            CREATE INDEX IF NOT EXISTS idx_est_venc ON estruturas(data_venc);

            CREATE TABLE IF NOT EXISTS legs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                estrutura_id INTEGER NOT NULL REFERENCES estruturas(id) ON DELETE CASCADE,
                operacao TEXT,
                tipo TEXT,
                qtd REAL,
                strike REAL,
                ticker TEXT,
                vencimento TEXT,
                premio REAL,
                iv REAL,
                delta REAL,
                gamma REAL,
                theta REAL,
                vega REAL
            );
            CREATE INDEX IF NOT EXISTS idx_legs_est ON legs(estrutura_id);
            CREATE INDEX IF NOT EXISTS idx_legs_tipo ON legs(tipo);
            CREATE INDEX IF NOT EXISTS idx_legs_strike ON legs(strike);
            CREATE INDEX IF NOT EXISTS idx_legs_venc ON legs(vencimento);
            CREATE INDEX IF NOT EXISTS idx_legs_ticker ON legs(ticker);
            """
        )
        c.commit()

    def backup(self, dest_path: Path | str) -> Path:
        """Cria backup da base de dados."""
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        self.connect()
        # Forçar checkpoint do WAL
        self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        shutil.copy2(self.path, dest)
        log.info("Backup criado: %s", dest)
        return dest

    def close(self) -> None:
        """Fecha a conexão com a base de dados."""
        if self._conn is not None:
            try:
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                self._conn.close()
            except Exception as e:
                log.warning("Erro ao fechar DB: %s", e)
            self._conn = None

    def get_all(self, store: str) -> list[dict[str, Any]]:
        conn = self.connect()
        table = "estruturas" if store == "estruturas" else "legs"
        cur = conn.execute(f"SELECT * FROM {table}")
        rows = cur.fetchall()
        if store == "estruturas":
            return [_row_estrutura(r) for r in rows]
        return [_row_leg(r) for r in rows]

    def get(self, store: str, key: int) -> Optional[dict[str, Any]]:
        conn = self.connect()
        table = "estruturas" if store == "estruturas" else "legs"
        cur = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (key,))
        row = cur.fetchone()
        if row is None:
            return None
        return _row_estrutura(row) if store == "estruturas" else _row_leg(row)

    def delete_row(self, store: str, key: int) -> None:
        conn = self.connect()
        table = "legs" if store == "legs" else "estruturas"
        conn.execute(f"DELETE FROM {table} WHERE id = ?", (key,))
        conn.commit()

    def save_estrutura(self, obj: dict[str, Any], *, autocommit: bool = True) -> int:
        conn = self.connect()
        if not obj.get("criadoEm"):
            obj["criadoEm"] = _now_iso()
        obj["atualizadoEm"] = _now_iso()
        oid = obj.get("id")
        if oid:
            conn.execute(
                """UPDATE estruturas SET nome=?, ativo=?, tipo=?, preco_atual=?, data_venc=?, obs=?, criado_em=?, atualizado_em=?
                   WHERE id=?""",
                (
                    obj.get("nome"),
                    obj.get("ativo"),
                    obj.get("tipo"),
                    obj.get("precoAtual"),
                    obj.get("dataVenc"),
                    obj.get("obs"),
                    obj.get("criadoEm"),
                    obj.get("atualizadoEm"),
                    oid,
                ),
            )
            if autocommit:
                conn.commit()
            return int(oid)
        cur = conn.execute(
            """INSERT INTO estruturas (nome, ativo, tipo, preco_atual, data_venc, obs, criado_em, atualizado_em)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                obj.get("nome"),
                obj.get("ativo"),
                obj.get("tipo"),
                obj.get("precoAtual"),
                obj.get("dataVenc"),
                obj.get("obs"),
                obj.get("criadoEm"),
                obj.get("atualizadoEm"),
            ),
        )
        if autocommit:
            conn.commit()
        return int(cur.lastrowid)

    def save_leg(self, obj: dict[str, Any], *, autocommit: bool = True) -> int:
        conn = self.connect()
        oid = obj.get("id")
        if oid:
            conn.execute(
                """UPDATE legs SET estrutura_id=?, operacao=?, tipo=?, qtd=?, strike=?, ticker=?, vencimento=?,
                   premio=?, iv=?, delta=?, gamma=?, theta=?, vega=? WHERE id=?""",
                (
                    obj.get("estruturaId"),
                    obj.get("operacao"),
                    obj.get("tipo"),
                    obj.get("qtd"),
                    obj.get("strike"),
                    obj.get("ticker"),
                    obj.get("vencimento"),
                    obj.get("premio"),
                    obj.get("iv"),
                    obj.get("delta"),
                    obj.get("gamma"),
                    obj.get("theta"),
                    obj.get("vega"),
                    oid,
                ),
            )
            if autocommit:
                conn.commit()
            return int(oid)
        cur = conn.execute(
            """INSERT INTO legs (estrutura_id, operacao, tipo, qtd, strike, ticker, vencimento,
               premio, iv, delta, gamma, theta, vega)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                obj.get("estruturaId"),
                obj.get("operacao"),
                obj.get("tipo"),
                obj.get("qtd"),
                obj.get("strike"),
                obj.get("ticker"),
                obj.get("vencimento"),
                obj.get("premio"),
                obj.get("iv"),
                obj.get("delta"),
                obj.get("gamma"),
                obj.get("theta"),
                obj.get("vega"),
            ),
        )
        if autocommit:
            conn.commit()
        return int(cur.lastrowid)

    def delete_estrutura(self, eid: int) -> None:
        conn = self.connect()
        conn.execute("DELETE FROM legs WHERE estrutura_id = ?", (eid,))
        conn.execute("DELETE FROM estruturas WHERE id = ?", (eid,))
        conn.commit()

    def get_estruturas(self) -> list[dict[str, Any]]:
        legs = self.get_all("legs")
        ests = self.get_all("estruturas")
        by_id: dict[int, int] = {}
        for lg in legs:
            eid = lg.get("estruturaId")
            if eid is not None:
                by_id[int(eid)] = by_id.get(int(eid), 0) + 1
        out = []
        for e in ests:
            eid = e.get("id")
            ee = dict(e)
            ee["_legsCount"] = by_id.get(int(eid), 0) if eid is not None else 0
            out.append(ee)
        out.sort(key=lambda x: x.get("id") or 0, reverse=True)
        return out

    def get_legs(self, estrutura_id: int) -> list[dict[str, Any]]:
        conn = self.connect()
        cur = conn.execute(
            "SELECT * FROM legs WHERE estrutura_id = ? ORDER BY id", (estrutura_id,)
        )
        return [_row_leg(r) for r in cur.fetchall()]

    def stats(self) -> dict[str, Any]:
        """Estatísticas rápidas da base de dados."""
        conn = self.connect()
        cur = conn.execute("SELECT COUNT(*) as cnt FROM estruturas")
        n_est = cur.fetchone()["cnt"]
        cur = conn.execute("SELECT COUNT(*) as cnt FROM legs")
        n_legs = cur.fetchone()["cnt"]
        return {"estruturas": n_est, "pernas": n_legs, "db_size_mb": round(self.path.stat().st_size / (1024 * 1024), 2)}


def get_db_path(instance_path: Path) -> Path:
    return instance_path / "eagle_opcoes_v2.sqlite"