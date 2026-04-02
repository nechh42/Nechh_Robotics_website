# WAR MACHINE -- MASTER GUIDE

Comprehensive Architecture, Risk Model and Upgrade Roadmap

------------------------------------------------------------------------

# 1. System Overview

War Machine is a multi‑strategy crypto futures trading system with
modular architecture.

Main characteristics:

-   Multi strategy engine
-   Regime detection
-   Adaptive strategy weights
-   Signal voting
-   Risk management modules
-   Automated execution

Typical pipeline:

Market Data ↓ Indicators ↓ Strategies ↓ Voting Engine ↓ Risk Engine ↓
Position Sizing ↓ Execution

------------------------------------------------------------------------

# 2. Project Structure

war_machine/

data/ - candle_manager.py - datafeed.py - sentiment.py

strategies/ - base.py - indicators.py - momentum.py - rsi_reversion.py -
vwap_reversion.py - regime.py

engine/ - orchestrator.py - adaptive_weights.py - voting.py -
opportunity_scanner.py

risk/ - position_sizer.py - stop_manager.py

execution/ - binance execution logic

monitoring/ - logs and metrics

------------------------------------------------------------------------

# 3. Indicator Layer

Indicators provide raw calculations.

Examples:

RSI EMA VWAP ATR

Example RSI:

calc_rsi(closes, period=14)

Indicators do not open trades.

They only supply data to strategies.

------------------------------------------------------------------------

# 4. Strategy Layer

Multiple strategies run simultaneously.

Momentum Strategy

Trend following.

Example logic:

price \> EMA momentum rising

→ LONG

RSI Reversion

Mean reversion.

RSI \< 30 → LONG RSI \> 70 → SHORT

VWAP Reversion

Price far from VWAP → trade toward VWAP

------------------------------------------------------------------------

# 5. Regime Detection

Regime module determines market state.

Examples:

TREND RANGE VOLATILE

Strategy weights adjust depending on regime.

Example:

TREND market momentum weight ↑

RANGE market reversion strategies ↑

------------------------------------------------------------------------

# 6. Voting System

Strategies generate signals.

Example:

Momentum → LONG RSI → SHORT VWAP → NONE

Voting engine calculates final signal.

------------------------------------------------------------------------

# 7. Risk Engine

Professional trading systems require layered risk control.

Current modules:

position sizing stop management

Recommended additional modules:

Correlation Filter Volatility Filter Daily Loss Kill Switch Exposure
Control

------------------------------------------------------------------------

# 8. Correlation Filter

Crypto markets are highly correlated.

Example:

ETH LONG SOL LONG AVAX LONG

This equals one BTC trade.

Filter example:

if correlation \> 0.8: block trade

------------------------------------------------------------------------

# 9. Volatility Filter

Extreme volatility can break strategies.

Example:

ATR / Price \> threshold → no trade

------------------------------------------------------------------------

# 10. Daily Loss Kill Switch

Professional trading desks stop trading after daily loss limits.

Example:

daily loss limit = 3%

if daily_loss \> limit: disable trading

------------------------------------------------------------------------

# 11. Edge Scoring Engine

Instead of binary signals:

signal → trade

Use scoring:

signal strength → trade size

Example:

momentum = 0.4 rsi = 0.3 vwap = 0.3

score = sum

Trade only if score \> threshold.

------------------------------------------------------------------------

# 12. Position Sizing

Professional bots size positions dynamically.

Example:

position = base_size \* edge_score

Higher confidence → larger trade.

------------------------------------------------------------------------

# 13. Exposure Control

Limit simultaneous exposure.

Examples:

max_open_positions = 5

max_same_direction = 3

max_coin_correlation = 0.8

------------------------------------------------------------------------

# 14. Performance Evaluation

Current sample example:

Trades: 6 Win Rate: 83% Profit Factor: 7

However small sample sizes are unreliable.

Real evaluation:

100 trades minimum 300 trades ideal

Important metrics:

Win Rate Profit Factor Expectancy Maximum Drawdown

------------------------------------------------------------------------

# 15. Target Metrics

Healthy system ranges:

Win Rate: 40--60% Profit Factor: \>1.4 Expectancy: positive Max
Drawdown: \<15%

------------------------------------------------------------------------

# 16. Future Upgrades (v6 Roadmap)

Recommended improvements:

1.  Correlation engine
2.  Volatility regime detection
3.  Dynamic leverage control
4.  Portfolio exposure model
5.  Edge scoring engine
6.  Walk‑forward testing
7.  Monte Carlo risk simulation
8.  Strategy performance tracking
9.  AI regime classification
10. Trade clustering limiter

------------------------------------------------------------------------

# 17. Institutional Architecture

Professional quant system structure:

Market Data ↓ Indicators ↓ Feature Engineering ↓ Strategies ↓ Signal
Scoring ↓ Risk Engine ↓ Portfolio Construction ↓ Execution Engine ↓
Monitoring

------------------------------------------------------------------------

# 18. Final Assessment

Architecture quality: strong Strategy diversity: good Risk control:
moderate Edge evidence: promising

Estimated system maturity:

7.5 / 10

With the upgrades above the system could approach institutional quant
trading architecture.
