"""simulator.py
Simulate trades considering slippage, gas fees, and placeholder DEX quotes.
"""
from typing import Dict, List, Any


def bps_to_fraction(bps: float) -> float:
    return max(float(bps) / 10000.0, 0.0)


def get_dex_quote(
    dex: str,
    token: str,
    side: str,
    amount: float,
    price: float,
    slippage_bps: float,
) -> float:
    """Placeholder DEX quote: adjust price by slippage in a side-aware way."""
    slip = bps_to_fraction(slippage_bps)
    if side == "buy":
        return price * (1.0 + slip)
    else:
        return price * (1.0 - slip)


def estimate_trade(
    trade: Dict[str, Any],
    price: float,
    slippage_bps: float,
    gas_cost_usd: float,
    dex: str,
) -> Dict[str, Any]:
    side = trade.get("side")
    amount = float(trade.get("amount", 0.0))
    quoted_price = get_dex_quote(dex, trade.get("token"), side, amount, price, slippage_bps)

    if side == "buy":
        cost_usd = amount * quoted_price + float(gas_cost_usd)
        return {
            "token": trade.get("token"),
            "side": side,
            "amount": amount,
            "quoted_price": quoted_price,
            "cost_usd": cost_usd,
        }
    else:
        proceeds_usd = amount * quoted_price - float(gas_cost_usd)
        if proceeds_usd < 0:
            proceeds_usd = 0.0
        return {
            "token": trade.get("token"),
            "side": side,
            "amount": amount,
            "quoted_price": quoted_price,
            "proceeds_usd": proceeds_usd,
        }


def simulate_trades(
    trades: List[Dict[str, Any]],
    prices: Dict[str, float],
    slippage_bps: float = 50.0,
    gas_cost_usd: float = 5.0,
    dex: str = "uniswap_v2",
) -> Dict[str, Any]:
    """Simulate a list of trades and provide per-trade and summary estimates."""
    results: List[Dict[str, Any]] = []
    total_buy_cost = 0.0
    total_sell_proceeds = 0.0
    total_gas_usd = 0.0

    for tr in trades:
        token = tr.get("token")
        price = float(prices.get(token, 0.0))
        if price <= 0:
            continue
        res = estimate_trade(tr, price, slippage_bps, gas_cost_usd, dex)
        results.append(res)
        if tr.get("side") == "buy":
            total_buy_cost += res.get("cost_usd", 0.0)
        else:
            total_sell_proceeds += res.get("proceeds_usd", 0.0)
        total_gas_usd += gas_cost_usd

    summary = {
        "total_buy_cost_usd": total_buy_cost,
        "total_sell_proceeds_usd": total_sell_proceeds,
        "net_usd_effect": total_sell_proceeds - total_buy_cost,
        "est_total_gas_usd": total_gas_usd,
    }
    return {"trades": results, "summary": summary}
