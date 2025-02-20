"""
Thoth Oracle Dashboard
A Bloomberg-style terminal for XRPL trading analytics
"""

import json
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
import numpy as np
import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import plotly.express as px
from xrpl.clients import JsonRpcClient
from xrpl.models import AccountLines, BookOffers

# Initialize the dashboard
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])
app.title = "Thoth Oracle Dashboard"

# Global state
class DashboardState:
    def __init__(self):
        self.trade_history = []
        self.liquidity_data = defaultdict(list)
        self.order_book_snapshots = defaultdict(list)
        self.trust_line_stats = defaultdict(dict)
        self.market_stats = defaultdict(dict)
        
        # Performance metrics
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.total_profit = 0.0
        
        # Risk metrics
        self.avg_market_impact = 0.0
        self.avg_execution_prob = 0.0
        self.avg_volatility = 0.0

state = DashboardState()

# Layout components
def create_header():
    return dbc.Row([
        dbc.Col(html.H1("Thoth Oracle Dashboard", className="text-primary"), width=8),
        dbc.Col([
            html.Div(id="clock", className="text-right h3"),
            html.Div(id="connection-status", className="text-right")
        ], width=4)
    ])

def create_metrics_row():
    return dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader("Trading Performance"),
            dbc.CardBody([
                html.H3(id="total-profit", className="text-success"),
                html.P("Total Profit (XRP)"),
                html.H4(id="trade-success-rate"),
                html.P("Success Rate"),
                html.Div(id="trade-counts")
            ])
        ])),
        dbc.Col(dbc.Card([
            dbc.CardHeader("Risk Metrics"),
            dbc.CardBody([
                html.H4(id="avg-market-impact"),
                html.P("Avg Market Impact"),
                html.H4(id="avg-execution-prob"),
                html.P("Avg Execution Probability"),
                html.H4(id="avg-volatility"),
                html.P("Avg Volatility")
            ])
        ])),
        dbc.Col(dbc.Card([
            dbc.CardHeader("Market Overview"),
            dbc.CardBody([
                html.H4(id="active-pairs"),
                html.P("Active Trading Pairs"),
                html.H4(id="total-liquidity"),
                html.P("Total DEX Liquidity (XRP)"),
                html.H4(id="opportunity-count"),
                html.P("Open Opportunities")
            ])
        ]))
    ])

def create_charts_row():
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Profit/Loss Timeline"),
                dbc.CardBody(dcc.Graph(id="pnl-chart"))
            ])
        ], width=8),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Risk Distribution"),
                dbc.CardBody(dcc.Graph(id="risk-chart"))
            ])
        ], width=4)
    ])

def create_order_book_row():
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.Span("Order Book Depth"),
                    dbc.Select(
                        id="pair-selector",
                        options=[],
                        placeholder="Select Trading Pair"
                    )
                ]),
                dbc.CardBody(dcc.Graph(id="order-book-chart"))
            ])
        ])
    ])

def create_trading_activity():
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Recent Trading Activity"),
                dbc.CardBody(
                    html.Div(id="trading-table", style={"height": "300px", "overflow": "auto"})
                )
            ])
        ], width=6),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Trust Line Status"),
                dbc.CardBody(
                    html.Div(id="trust-line-table", style={"height": "300px", "overflow": "auto"})
                )
            ])
        ], width=6)
    ])

# Main layout
app.layout = dbc.Container([
    create_header(),
    html.Hr(),
    create_metrics_row(),
    html.Br(),
    create_charts_row(),
    html.Br(),
    create_order_book_row(),
    html.Br(),
    create_trading_activity(),
    dcc.Interval(id="update-interval", interval=1000, n_intervals=0)
], fluid=True, style={"backgroundColor": "#1a1a1a", "minHeight": "100vh"})

# Callbacks
@app.callback(
    [Output("clock", "children"),
     Output("total-profit", "children"),
     Output("trade-success-rate", "children"),
     Output("trade-counts", "children"),
     Output("avg-market-impact", "children"),
     Output("avg-execution-prob", "children"),
     Output("avg-volatility", "children")],
    Input("update-interval", "n_intervals")
)
def update_metrics(n):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Calculate success rate
    success_rate = (state.successful_trades / state.total_trades * 100 
                   if state.total_trades > 0 else 0)
    
    return (
        current_time,
        f"₽ {state.total_profit:,.2f}",
        f"{success_rate:.1f}%",
        f"Total: {state.total_trades} | Success: {state.successful_trades} | Failed: {state.failed_trades}",
        f"{state.avg_market_impact:.2%}",
        f"{state.avg_execution_prob:.2%}",
        f"{state.avg_volatility:.2%}"
    )

@app.callback(
    Output("pnl-chart", "figure"),
    Input("update-interval", "n_intervals")
)
def update_pnl_chart(n):
    if not state.trade_history:
        return go.Figure()
    
    df = pd.DataFrame(state.trade_history)
    df["cumulative_profit"] = df["profit"].cumsum()
    
    fig = px.line(
        df, x="timestamp", y="cumulative_profit",
        title="Cumulative Profit/Loss"
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    return fig

@app.callback(
    Output("risk-chart", "figure"),
    Input("update-interval", "n_intervals")
)
def update_risk_chart(n):
    if not state.trade_history:
        return go.Figure()
    
    df = pd.DataFrame(state.trade_history)
    
    fig = go.Figure()
    fig.add_trace(go.Box(
        y=df["market_impact"],
        name="Market Impact",
        boxpoints="all"
    ))
    fig.add_trace(go.Box(
        y=df["execution_prob"],
        name="Execution Prob",
        boxpoints="all"
    ))
    fig.add_trace(go.Box(
        y=df["volatility"],
        name="Volatility",
        boxpoints="all"
    ))
    
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        title="Risk Metrics Distribution"
    )
    return fig

@app.callback(
    Output("order-book-chart", "figure"),
    [Input("update-interval", "n_intervals"),
     Input("pair-selector", "value")]
)
def update_order_book(n, pair):
    if not pair or not state.order_book_snapshots[pair]:
        return go.Figure()
    
    latest = state.order_book_snapshots[pair][-1]
    bids = pd.DataFrame(latest["bids"])
    asks = pd.DataFrame(latest["asks"])
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=bids["price"], y=bids["amount"],
        fill="tozeroy",
        name="Bids",
        line=dict(color="green")
    ))
    fig.add_trace(go.Scatter(
        x=asks["price"], y=asks["amount"],
        fill="tozeroy",
        name="Asks",
        line=dict(color="red")
    ))
    
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        title=f"Order Book Depth - {pair}"
    )
    return fig

@app.callback(
    Output("trading-table", "children"),
    Input("update-interval", "n_intervals")
)
def update_trading_table(n):
    if not state.trade_history:
        return "No trades yet"
    
    recent_trades = state.trade_history[-10:]  # Last 10 trades
    rows = []
    for trade in reversed(recent_trades):
        rows.append(html.Tr([
            html.Td(trade["timestamp"].strftime("%H:%M:%S")),
            html.Td(trade["pair"]),
            html.Td(f"{trade['size']} {trade['base_currency']}"),
            html.Td(f"₽ {trade['profit']:.2f}", className="text-success" if trade["profit"] > 0 else "text-danger")
        ]))
    
    return dbc.Table([html.Tbody(rows)], bordered=True, dark=True, hover=True)

@app.callback(
    Output("trust-line-table", "children"),
    Input("update-interval", "n_intervals")
)
def update_trust_line_table(n):
    if not state.trust_line_stats:
        return "No trust lines"
    
    rows = []
    for currency, stats in state.trust_line_stats.items():
        rows.append(html.Tr([
            html.Td(currency),
            html.Td(stats["issuer"]),
            html.Td(stats["limit"]),
            html.Td(stats["balance"])
        ]))
    
    return dbc.Table([html.Tbody(rows)], bordered=True, dark=True, hover=True)

if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
