"""
risk_manager.py
Menghitung ukuran posisi (lot) yang aman berdasarkan aturan risk-per-trade
dan batas alokasi maksimal per saham. 1 Lot = 100 lembar (aturan BEI).
"""

import math


class RiskManager:
    def __init__(self, total_capital: float, risk_per_trade_pct: float = 0.02,
                 max_allocation_pct: float = 0.20):
        if total_capital <= 0:
            raise ValueError("Modal harus lebih besar dari 0")
        self.total_capital = total_capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_allocation_pct = max_allocation_pct

    def calculate_position_size(self, entry_price: float, stop_loss_price: float):
        if stop_loss_price >= entry_price:
            raise ValueError("Stop loss harus lebih rendah dari harga entry")

        max_risk_amount = self.total_capital * self.risk_per_trade_pct
        risk_per_share = entry_price - stop_loss_price

        shares_by_risk = max_risk_amount / risk_per_share
        max_position_value = self.total_capital * self.max_allocation_pct
        shares_by_allocation = max_position_value / entry_price

        final_shares = min(shares_by_risk, shares_by_allocation)
        final_lots = math.floor(final_shares / 100)
        total_investment = final_lots * 100 * entry_price

        return {
            "lots": final_lots,
            "shares": final_lots * 100,
            "total_investment": total_investment,
            "max_risk_amount": max_risk_amount,
            "limited_by": "risiko" if shares_by_risk < shares_by_allocation else "alokasi maksimal",
        }
