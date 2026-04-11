"""
Módulo de notificação via e-mail para opções próximas do vencimento.
Verifica se as opções serão exercidas e envia relatório.
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import List, Dict, Tuple

from system.ui.logger import get_logger
from system.core.db import Database
from system import config

log = get_logger("email_notifier")


class EmailNotifier:
    """Gerencia notificações de opções próximas do vencimento via e-mail."""

    def __init__(self):
        self.smtp_server = config.SMTP_SERVER
        self.smtp_port = config.SMTP_PORT
        self.from_email = config.FROM_EMAIL
        self.email_password = config.EMAIL_PASSWORD
        self.to_email = config.TO_EMAIL
        self.dias_alerta = config.DIAS_ALERTA

    def _conectar_smtp(self) -> smtplib.SMTP:
        """Conecta ao servidor SMTP."""
        try:
            if self.smtp_port == 587:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=10)
            
            server.login(self.from_email, self.email_password)
            log.info("Conectado ao servidor SMTP: %s", self.smtp_server)
            return server
        except smtplib.SMTPException as e:
            log.error("Erro ao conectar SMTP: %s", e)
            raise

    def _vai_ser_exercida(
        self, tipo: str, spot: float, strike: float, intrinseco: float
    ) -> Tuple[bool, str]:
        """
        Determina se a opção será exercida (ITM = In The Money).
        
        Args:
            tipo: 'CALL' ou 'PUT'
            spot: Preço do ativo subjacente
            strike: Strike da opção
            intrinseco: Valor intrínseco
            
        Returns:
            (será_exercida, status_str)
        """
        if tipo.upper() == "CALL":
            if intrinseco > 0:  # S > K (ITM)
                return True, f"SIM - ITM (S={spot:.2f} > K={strike:.2f})"
            else:
                return False, f"NÃO - OTM (S={spot:.2f} ≤ K={strike:.2f})"
        else:  # PUT
            if intrinseco > 0:  # K > S (ITM)
                return True, f"SIM - ITM (K={strike:.2f} > S={spot:.2f})"
            else:
                return False, f"NÃO - OTM (K={strike:.2f} ≤ S={spot:.2f})"

    def obter_opcoes_proximas_vencimento(self, db: Database) -> List[Dict]:
        """
        Obtém todas as opções em estruturas que vencem em <= DIAS_ALERTA dias.
        """
        data_limite = datetime.now().date() + timedelta(days=self.dias_alerta)

        query = """
        SELECT 
            e.id as estrutura_id,
            e.nome as estrutura_nome,
            l.id as leg_id,
            l.tipo,
            l.strike,
            l.vencimento,
            JULIANDAY(l.vencimento) - JULIANDAY('now') as dias_faltam,
            e.preco_atual as preco_spot,
            l.premio as preco_atual,
            l.operacao
        FROM legs l
        JOIN estruturas e ON l.estrutura_id = e.id
        WHERE l.vencimento <= ?
        AND l.vencimento > DATE('now')
        ORDER BY l.vencimento ASC, e.id ASC
        """

        conn = db.connect()                          # ← usa o método público
        cursor = conn.cursor()
        cursor.execute(query, (data_limite.isoformat(),))
        rows = cursor.fetchall()

        opcoes_proximas = []
        for row in rows:
            estrutura_id  = row["estrutura_id"]
            estrutura_nome = row["estrutura_nome"]
            leg_id        = row["leg_id"]
            tipo          = row["tipo"]
            strike        = row["strike"]
            vencimento    = row["vencimento"]
            dias_faltam   = row["dias_faltam"]
            preco_spot    = row["preco_spot"] or 0.0   # preco_atual da estrutura
            preco_atual   = row["preco_atual"] or 0.0  # premio da leg
            operacao      = row["operacao"]

            # Valor intrínseco baseado no spot da estrutura e strike da leg
            if tipo and tipo.upper() == "CALL":
                intrinseco = max(0.0, preco_spot - strike)
            else:
                intrinseco = max(0.0, strike - preco_spot)

            sera_exercida, status = self._vai_ser_exercida(
                tipo or "", preco_spot, strike or 0.0, intrinseco
            )

            opcoes_proximas.append({
                "estrutura_id":   estrutura_id,
                "estrutura_nome": estrutura_nome,
                "leg_id":         leg_id,
                "tipo":           tipo,
                "strike":         strike or 0.0,
                "vencimento":     vencimento,
                "dias_faltam":    round(dias_faltam, 1) if dias_faltam else 0,
                "preco_spot":     preco_spot,
                "preco_atual":    preco_atual,
                "operacao":       operacao,
                "intrinseco":     intrinseco,
                "sera_exercida":  sera_exercida,
                "status":         status,
            })

        cursor.close()
        return opcoes_proximas

    def _gerar_html_email(self, opcoes: List[Dict]) -> str:
        """Gera o corpo HTML do e-mail."""
        if not opcoes:
            return "<p>Nenhuma opção próxima do vencimento.</p>"
        
        # Agrupar por estrutura
        estruturas_agrupadas = {}
        for op in opcoes:
            eid = op["estrutura_id"]
            if eid not in estruturas_agrupadas:
                estruturas_agrupadas[eid] = {
                    "nome": op["estrutura_nome"],
                    "legs": []
                }
            estruturas_agrupadas[eid]["legs"].append(op)
        
        html_tabelas = []
        for eid, dados_est in estruturas_agrupadas.items():
            linhas = ""
            for leg in dados_est["legs"]:
                cor_exercicio = "#4CAF50" if leg["sera_exercida"] else "#FF9800"  # Verde ou Laranja
                linhas += f"""
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd;">{leg['tipo']}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd;">R$ {leg['strike']:.2f}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd;">{leg['vencimento']}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd;">{leg['dias_faltam']} dias</td>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd;">R$ {leg['preco_spot']:.2f}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd;">R$ {leg['intrinseco']:.2f}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd; color: white; background-color: {cor_exercicio}; font-weight: bold;">
                        {leg['status']}
                    </td>
                </tr>
                """
            
            html_tabelas.append(f"""
            <div style="margin-bottom: 20px; background-color: #f9f9f9; padding: 15px; border-radius: 5px; border-left: 4px solid #2196F3;">
                <h3 style="color: #2196F3; margin: 0 0 10px 0;">📊 {dados_est['nome']}</h3>
                <table style="width: 100%; border-collapse: collapse; background-color: white; border-radius: 3px;">
                    <thead>
                        <tr style="background-color: #2196F3; color: white;">
                            <th style="padding: 10px; text-align: left;">Tipo</th>
                            <th style="padding: 10px; text-align: left;">Strike</th>
                            <th style="padding: 10px; text-align: left;">Vencimento</th>
                            <th style="padding: 10px; text-align: left;">Dias</th>
                            <th style="padding: 10px; text-align: left;">Spot</th>
                            <th style="padding: 10px; text-align: left;">Intrínseco</th>
                            <th style="padding: 10px; text-align: left;">Será Exercida?</th>
                        </tr>
                    </thead>
                    <tbody>
                        {linhas}
                    </tbody>
                </table>
            </div>
            """)
        
        html = f"""
        <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: Arial, sans-serif; color: #333; }}
                    h2 {{ color: #2196F3; margin-bottom: 20px; }}
                    .header {{ background-color: #2196F3; color: white; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                    .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ccc; font-size: 12px; color: #666; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h2>🔔 Alerta de Opções Próximas ao Vencimento</h2>
                    <p>Data/hora: {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}</p>
                    <p>Estruturas com vencimento em até <strong>{self.dias_alerta} dias</strong></p>
                </div>
                
                {''.join(html_tabelas)}
                
                <div class="footer">
                    <p><strong>Legenda:</strong></p>
                    <ul>
                        <li><span style="color: white; background-color: #4CAF50; padding: 2px 5px; border-radius: 3px;"><strong>SIM (Verde)</strong></span> = Opção será exercida (ITM)</li>
                        <li><span style="color: white; background-color: #FF9800; padding: 2px 5px; border-radius: 3px;"><strong>NÃO (Laranja)</strong></span> = Opção não será exercida (OTM)</li>
                    </ul>
                    <p>Este é um alerta automático do Yuri System. Verifique os dados na plataforma antes de tomar decisões.</p>
                </div>
            </body>
        </html>
        """
        
        return html

    def enviar_notificacao(self, db: Database) -> bool:
        """
        Envia notificação de opções próximas do vencimento.
        
        Returns:
            True se enviado com sucesso, False caso contrário
        """
        try:
            # Obter opções próximas
            opcoes = self.obter_opcoes_proximas_vencimento(db)
            
            if not opcoes:
                log.info("Nenhuma opção próxima do vencimento para notificar")
                return False
            
            log.info("Encontradas %d opções próximas do vencimento", len(opcoes))
            
            # Gerar e-mail
            msg = MIMEMultipart("alternative")
            msg["From"] = self.from_email
            msg["To"] = self.to_email
            msg["Subject"] = f"🔔 Yuri System - Alerta de {len(opcoes)} Opção(ões) Próximas ao Vencimento"
            
            # Corpo HTML
            html_body = self._gerar_html_email(opcoes)
            msg.attach(MIMEText(html_body, "html", _charset="utf-8"))
            
            # Enviar
            server = self._conectar_smtp()
            server.send_message(msg)
            server.quit()
            
            log.info("E-mail de notificação enviado para: %s", self.to_email)
            return True
            
        except Exception as e:
            log.error("Erro ao enviar notificação: %s", e)
            return False


def criar_notificador() -> EmailNotifier:
    """Factory para criar instância de EmailNotifier."""
    return EmailNotifier()
