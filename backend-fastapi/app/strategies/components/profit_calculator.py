from typing import List, Dict


class ProfitCalculator:
    """Модуль для расчета прибыли"""

    def __init__(self):
        pass

    def get_total_profit_usdt(self, realized_profit_a: float, realized_profit_b: float, current_price: float) -> float:
        """Рассчитывает общую прибыль в USDT"""
        profit_b_in_usdt = realized_profit_b * current_price
        total_profit_usdt = realized_profit_a + profit_b_in_usdt
        return total_profit_usdt

    def calculate_unrealized_profit_loss(self, open_trades: List[Dict], current_price: float) -> Dict[str, float]:
        """Рассчитывает нереализованную прибыль или убыток от открытых сделок"""
        unrealized_profit_a = 0.0
        unrealized_profit_b = 0.0

        for trade in open_trades:
            if trade.get('order_type') == 'buy':
                buy_price = trade['price']
                quantity = trade['quantity']
                profit_a = (current_price - buy_price) * quantity
                unrealized_profit_a += profit_a
            elif trade.get('order_type') == 'sell':
                sell_price = trade['price']
                quantity = trade['quantity']
                profit_b = quantity * ((sell_price / current_price) - 1)
                unrealized_profit_b += profit_b

        total_unrealized_profit_usdt = unrealized_profit_a + (unrealized_profit_b * current_price)

        return {
            "unrealized_profit_a": unrealized_profit_a,
            "unrealized_profit_b": unrealized_profit_b,
            "total_unrealized_profit_usdt": total_unrealized_profit_usdt
        } 