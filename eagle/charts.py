"""
Gráficos Plotly — equivalente a js/chart.js + dashboard Chart.js.
"""

from __future__ import annotations

from typing import Optional

import plotly.graph_objects as go

from eagle import blackscholes as BS
from eagle.ui_format import brl

COLORS = {
    "profit_line": "#4ade80",
    "profit_fill": "rgba(74, 222, 128, 0.20)",
    "loss_line": "#f87171",
    "loss_fill": "rgba(248, 113, 113, 0.20)",
    "current": "#fbbf24",
    "current_fill": "rgba(251, 191, 36, 0.08)",
    "spot": "#60a5fa",
    "zero": "rgba(255,255,255,0.15)",
    "grid": "rgba(255,255,255,0.05)",
    "tick": "#555c70",
    "bg": "#1a1e2a",
}


def payoff_figure(
    estrutura: dict,
    legs: list,
    show_current: bool = True,
) -> Optional[str]:
    """Retorna HTML parcial (div) do Plotly ou None."""
    if not legs:
        return None
    data = BS.compute_payoff_series(estrutura, legs)
    if not data:
        return None

    labels = data["labels"]
    payoff_expiry = data["payoffExpiry"]
    payoff_current = data.get("payoffCurrent")
    s0 = float(data.get("S0") or 0)
    t_val = float(data.get("T") or 0)

    pos_exp = [v if v >= 0 else 0 for v in payoff_expiry]
    neg_exp = [v if v < 0 else 0 for v in payoff_expiry]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=labels,
            y=pos_exp,
            name="Lucro (Exp.)",
            line=dict(color=COLORS["profit_line"], width=2),
            fill="tozeroy",
            fillcolor=COLORS["profit_fill"],
            mode="lines",
            hovertemplate="P&L Exp.: %{customdata}<extra></extra>",
            customdata=[brl(v) for v in pos_exp],
        )
    )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=neg_exp,
            name="Perda (Exp.)",
            line=dict(color=COLORS["loss_line"], width=2),
            fill="tozeroy",
            fillcolor=COLORS["loss_fill"],
            mode="lines",
            hovertemplate="P&L Exp.: %{customdata}<extra></extra>",
            customdata=[brl(v) for v in neg_exp],
        )
    )

    if show_current and payoff_current and t_val > 0.001:
        pos_cur = [v if v >= 0 else 0 for v in payoff_current]
        neg_cur = [v if v < 0 else 0 for v in payoff_current]
        fig.add_trace(
            go.Scatter(
                x=labels,
                y=pos_cur,
                name="Lucro (Atual BS)",
                line=dict(color=COLORS["current"], width=1.5, dash="dash"),
                fill="tozeroy",
                fillcolor=COLORS["current_fill"],
                mode="lines",
                hovertemplate="P&L Atual (BS): %{customdata}<extra></extra>",
                customdata=[brl(v) for v in pos_cur],
            )
        )
        fig.add_trace(
            go.Scatter(
                x=labels,
                y=neg_cur,
                name="Perda (Atual BS)",
                line=dict(color=COLORS["current"], width=1.5, dash="dash"),
                mode="lines",
                hovertemplate="P&L Atual (BS): %{customdata}<extra></extra>",
                customdata=[brl(v) for v in neg_cur],
            )
        )

    all_y = payoff_expiry[:]
    if payoff_current:
        all_y = all_y + payoff_current
    y_min = min(all_y) if all_y else 0
    y_max = max(all_y) if all_y else 1
    pad = max(abs(y_max - y_min) * 0.05, 1.0)

    fig.add_hline(y=0, line_color=COLORS["zero"], line_width=1)
    if s0 > 0:
        fig.add_vline(
            x=s0,
            line_color=COLORS["spot"],
            line_width=1.5,
            line_dash="dot",
            annotation_text=f"Spot: {brl(s0)}",
            annotation_position="top",
            annotation=dict(font=dict(color=COLORS["spot"], size=11), bgcolor="rgba(96,165,250,0.15)"),
        )

    fig.update_yaxes(range=[y_min - pad, y_max + pad])

    fig.update_layout(
        showlegend=False,
        margin=dict(l=50, r=20, t=30, b=40),
        paper_bgcolor=COLORS["bg"],
        plot_bgcolor=COLORS["bg"],
        font=dict(color=COLORS["tick"], size=11),
        hovermode="x unified",
        xaxis=dict(
            title="Preço do ativo",
            gridcolor=COLORS["grid"],
            tickformat=".2f",
            tickprefix="R$",
            zeroline=False,
        ),
        yaxis=dict(
            title="P&L",
            gridcolor=COLORS["grid"],
            zeroline=False,
        ),
        height=420,
    )

    return fig.to_html(
        full_html=False,
        include_plotlyjs="cdn",
        config={"displayModeBar": True, "responsive": True},
    )


def dashboard_doughnut(tipo_map: dict[str, int], include_plotlyjs: bool | str = False) -> str:
    if not tipo_map:
        return ""
    labels = list(tipo_map.keys())
    values = list(tipo_map.values())
    colors = [
        "#4ade80",
        "#60a5fa",
        "#fbbf24",
        "#a78bfa",
        "#f87171",
        "#22d3ee",
        "#f472b6",
        "#fb923c",
    ]
    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.55,
                marker=dict(colors=colors[: len(labels)]),
            )
        ]
    )
    fig.update_layout(
        paper_bgcolor=COLORS["bg"],
        plot_bgcolor=COLORS["bg"],
        font=dict(color="#8b90a0", size=11),
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=True,
        legend=dict(font=dict(size=11)),
        height=280,
    )
    return fig.to_html(
        full_html=False,
        include_plotlyjs=include_plotlyjs,
        config={"responsive": True},
    )


def dashboard_bar(est_names: list[str], est_premios: list[float], include_plotlyjs: bool | str = False) -> str:
    if not est_names:
        return ""
    colors = [
        "rgba(74,222,128,0.6)" if v >= 0 else "rgba(248,113,113,0.6)" for v in est_premios
    ]
    fig = go.Figure(
        data=[
            go.Bar(
                x=est_names,
                y=est_premios,
                marker_color=colors,
            )
        ]
    )
    fig.update_layout(
        paper_bgcolor=COLORS["bg"],
        plot_bgcolor=COLORS["bg"],
        font=dict(color="#8b90a0", size=10),
        margin=dict(l=50, r=20, t=10, b=80),
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)", tickangle=-25),
        yaxis=dict(
            gridcolor="rgba(255,255,255,0.05)",
            tickprefix="R$ ",
        ),
        showlegend=False,
        height=280,
    )
    return fig.to_html(
        full_html=False,
        include_plotlyjs=include_plotlyjs,
        config={"responsive": True},
    )
