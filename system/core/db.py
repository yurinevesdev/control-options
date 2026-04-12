"""
Camada de persistência SQLite — equivalente lógico a js/db.js (system_opcoes_v2).
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

from system.ui.logger import get_logger

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
        "status": row["status"] or "em_andamento",
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


def _row_carteira(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "nome": row["nome"],
        "descricao": row["descricao"],
        "dataInicio": row["data_inicio"],
        "criadoEm": row["criado_em"],
        "atualizadoEm": row["atualizado_em"],
    }


def _row_ativo_carteira(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "carteiraId": row["carteira_id"],
        "ticker": row["ticker"],
        "quantidade": row["quantidade"],
        "precoMedio": row["preco_medio"],
        "alocacaoIdeal": row["alocacao_ideal"],
        "precoAtual": row["preco_atual"],
        "atualizadoEmPreco": row["atualizado_em_preco"],
        "criadoEm": row["criado_em"],
        "atualizadoEm": row["atualizado_em"],
    }


class Database:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn: Optional[sqlite3.Connection] = None
            try:
                conn = sqlite3.connect(self.path, check_same_thread=False)
                conn.row_factory = sqlite3.Row

                foreign_keys_cursor = conn.execute("PRAGMA foreign_keys = ON")
                foreign_keys_cursor.close()

                # `journal_mode = WAL` pode causar transição interna de estado na conexão.
                # Consumimos e fechamos o cursor explicitamente antes de seguir.
                journal_mode_cursor = conn.execute("PRAGMA journal_mode = WAL")
                journal_mode_cursor.fetchone()
                journal_mode_cursor.close()

                self._conn = conn
                self._init_schema()
            except Exception:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass
                self._conn = None
                raise
        return self._conn

    def _init_schema(self) -> None:
        c = self._conn
        assert c is not None

        import logging
        log = logging.getLogger(__name__)

        # Criar tabela base sem status (para compatibilidade)
        c.execute(
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
            )
            """
        )

        # Índices básicos
        c.execute("CREATE INDEX IF NOT EXISTS idx_est_criado ON estruturas(criado_em)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_est_tipo ON estruturas(tipo)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_est_ativo ON estruturas(ativo)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_est_venc ON estruturas(data_venc)")

        # Tabela legs
        c.execute(
            """
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
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_legs_est ON legs(estrutura_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_legs_tipo ON legs(tipo)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_legs_strike ON legs(strike)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_legs_venc ON legs(vencimento)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_legs_ticker ON legs(ticker)")

        # Tabela carteiras
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS carteiras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                descricao TEXT,
                data_inicio TEXT,
                criado_em TEXT,
                atualizado_em TEXT
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_cart_criado ON carteiras(criado_em)")

        # Tabela ativos_carteira
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS ativos_carteira (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                carteira_id INTEGER NOT NULL REFERENCES carteiras(id) ON DELETE CASCADE,
                ticker TEXT NOT NULL,
                quantidade REAL NOT NULL,
                preco_medio REAL NOT NULL,
                alocacao_ideal REAL NOT NULL,
                preco_atual REAL,
                atualizado_em_preco TEXT,
                criado_em TEXT,
                atualizado_em TEXT
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_ativo_carteira ON ativos_carteira(carteira_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ativo_ticker ON ativos_carteira(ticker)")

        # Migração: adicionar coluna status se não existir (bancos antigos)
        try:
            c.execute("ALTER TABLE estruturas ADD COLUMN status TEXT DEFAULT 'em_andamento'")
            log.info("Coluna 'status' adicionada à tabela estruturas")
        except Exception:
            pass  # Coluna já existe

        # Índice de status (só após coluna existir)
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_est_status ON estruturas(status)")
        except Exception:
            pass

        # Commit final
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
                """UPDATE estruturas SET nome=?, ativo=?, tipo=?, preco_atual=?, data_venc=?, obs=?, status=?, criado_em=?, atualizado_em=?
                   WHERE id=?""",
                (
                    obj.get("nome"),
                    obj.get("ativo"),
                    obj.get("tipo"),
                    obj.get("precoAtual"),
                    obj.get("dataVenc"),
                    obj.get("obs"),
                    obj.get("status", "em_andamento"),
                    obj.get("criadoEm"),
                    obj.get("atualizadoEm"),
                    oid,
                ),
            )
            if autocommit:
                conn.commit()
            return int(oid)
        cur = conn.execute(
            """INSERT INTO estruturas (nome, ativo, tipo, preco_atual, data_venc, obs, status, criado_em, atualizado_em)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                obj.get("nome"),
                obj.get("ativo"),
                obj.get("tipo"),
                obj.get("precoAtual"),
                obj.get("dataVenc"),
                obj.get("obs"),
                obj.get("status", "em_andamento"),
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

    def update_status_estrutura(self, eid: int, status: str) -> None:
        """Atualiza apenas o status de uma estrutura."""
        conn = self.connect()
        conn.execute("UPDATE estruturas SET status = ?, atualizado_em = ? WHERE id = ?", (status, _now_iso(), eid))
        conn.commit()

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

    # ==================== Carteira Methods ====================

    def save_carteira(self, obj: dict[str, Any], *, autocommit: bool = True) -> int:
        """Criar/editar carteira"""
        conn = self.connect()
        if not obj.get("criadoEm"):
            obj["criadoEm"] = _now_iso()
        obj["atualizadoEm"] = _now_iso()

        oid = obj.get("id")
        if oid:
            conn.execute(
                """UPDATE carteiras SET nome=?, descricao=?, data_inicio=?, criado_em=?, atualizado_em=?
                   WHERE id=?""",
                (
                    obj.get("nome"),
                    obj.get("descricao"),
                    obj.get("dataInicio"),
                    obj.get("criadoEm"),
                    obj.get("atualizadoEm"),
                    oid,
                ),
            )
            if autocommit:
                conn.commit()
            return int(oid)

        cur = conn.execute(
            """INSERT INTO carteiras (nome, descricao, data_inicio, criado_em, atualizado_em)
               VALUES (?,?,?,?,?)""",
            (
                obj.get("nome"),
                obj.get("descricao"),
                obj.get("dataInicio"),
                obj.get("criadoEm"),
                obj.get("atualizadoEm"),
            ),
        )
        if autocommit:
            conn.commit()
        return int(cur.lastrowid)

    def get_carteira(self, cart_id: int) -> Optional[dict[str, Any]]:
        """Obter carteira por ID"""
        conn = self.connect()
        cur = conn.execute("SELECT * FROM carteiras WHERE id = ?", (cart_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return _row_carteira(row)

    def get_carteiras(self) -> list[dict[str, Any]]:
        """Obter todas as carteiras"""
        conn = self.connect()
        cur = conn.execute("SELECT * FROM carteiras ORDER BY id DESC")
        return [_row_carteira(r) for r in cur.fetchall()]

    def delete_carteira(self, cart_id: int) -> None:
        """Deletar carteira (e todos os ativos associados via CASCADE)"""
        conn = self.connect()
        conn.execute("DELETE FROM ativos_carteira WHERE carteira_id = ?", (cart_id,))
        conn.execute("DELETE FROM carteiras WHERE id = ?", (cart_id,))
        conn.commit()

    # ==================== Ativo Carteira Methods ====================

    def save_ativo_carteira(self, obj: dict[str, Any], *, autocommit: bool = True) -> int:
        """Criar/editar ativo na carteira"""
        conn = self.connect()
        if not obj.get("criadoEm"):
            obj["criadoEm"] = _now_iso()
        obj["atualizadoEm"] = _now_iso()
        obj["atualizadoEmPreco"] = _now_iso()

        oid = obj.get("id")
        if oid:
            conn.execute(
                """UPDATE ativos_carteira SET carteira_id=?, ticker=?, quantidade=?, preco_medio=?,
                   alocacao_ideal=?, preco_atual=?, atualizado_em_preco=?, criado_em=?, atualizado_em=?
                   WHERE id=?""",
                (
                    obj.get("carteiraId"),
                    obj.get("ticker"),
                    obj.get("quantidade"),
                    obj.get("precoMedio"),
                    obj.get("alocacaoIdeal"),
                    obj.get("precoAtual"),
                    obj.get("atualizadoEmPreco"),
                    obj.get("criadoEm"),
                    obj.get("atualizadoEm"),
                    oid,
                ),
            )
            if autocommit:
                conn.commit()
            return int(oid)

        cur = conn.execute(
            """INSERT INTO ativos_carteira (carteira_id, ticker, quantidade, preco_medio,
               alocacao_ideal, preco_atual, atualizado_em_preco, criado_em, atualizado_em)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                obj.get("carteiraId"),
                obj.get("ticker"),
                obj.get("quantidade"),
                obj.get("precoMedio"),
                obj.get("alocacaoIdeal"),
                obj.get("precoAtual"),
                obj.get("atualizadoEmPreco"),
                obj.get("criadoEm"),
                obj.get("atualizadoEm"),
            ),
        )
        if autocommit:
            conn.commit()
        return int(cur.lastrowid)

    def get_ativo_carteira(self, ativo_id: int) -> Optional[dict[str, Any]]:
        """Obter ativo da carteira por ID"""
        conn = self.connect()
        cur = conn.execute("SELECT * FROM ativos_carteira WHERE id = ?", (ativo_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return _row_ativo_carteira(row)

    def get_ativos_carteira(self, cart_id: int) -> list[dict[str, Any]]:
        """Obter todos os ativos de uma carteira"""
        conn = self.connect()
        cur = conn.execute("SELECT * FROM ativos_carteira WHERE carteira_id = ? ORDER BY id", (cart_id,))
        return [_row_ativo_carteira(r) for r in cur.fetchall()]

    def delete_ativo_carteira(self, ativo_id: int) -> None:
        """Deletar ativo da carteira"""
        conn = self.connect()
        conn.execute("DELETE FROM ativos_carteira WHERE id = ?", (ativo_id,))
        conn.commit()

    def atualizar_preco_ativo(self, ativo_id: int, preco: float) -> None:
        """Atualizar preço de um ativo"""
        conn = self.connect()
        conn.execute(
            "UPDATE ativos_carteira SET preco_atual = ?, atualizado_em_preco = ? WHERE id = ?",
            (preco, _now_iso(), ativo_id),
        )
        conn.commit()

    def stats(self) -> dict[str, Any]:
        """Estatísticas rápidas da base de dados."""
        conn = self.connect()
        cur = conn.execute("SELECT COUNT(*) as cnt FROM estruturas")
        n_est = cur.fetchone()["cnt"]
        cur = conn.execute("SELECT COUNT(*) as cnt FROM legs")
        n_legs = cur.fetchone()["cnt"]
        cur = conn.execute("SELECT COUNT(*) as cnt FROM carteiras")
        n_cart = cur.fetchone()["cnt"]
        cur = conn.execute("SELECT COUNT(*) as cnt FROM ativos_carteira")
        n_ativos_cart = cur.fetchone()["cnt"]
        return {
            "estruturas": n_est,
            "pernas": n_legs,
            "carteiras": n_cart,
            "ativos_carteira": n_ativos_cart,
            "db_size_mb": round(self.path.stat().st_size / (1024 * 1024), 2),
        }


def get_db_path(instance_path: Path) -> Path:
    return instance_path / "system_opcoes_v2.sqlite"
