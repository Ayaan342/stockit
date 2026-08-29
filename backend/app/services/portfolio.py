from decimal import Decimal, ROUND_HALF_UP

from app.models.portfolio import Holding, Transaction
from app.schemas.portfolio import HoldingResponse

MONEY_QUANTUM = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def holding_response(holding: Holding, current_price: Decimal) -> HoldingResponse:
    invested_value = money(holding.quantity * holding.average_buy_price)
    current_value = money(holding.quantity * current_price)
    profit_loss = money(current_value - invested_value)
    percentage = None
    if holding.average_buy_price > 0:
        percentage = ((current_price - holding.average_buy_price) / holding.average_buy_price * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    return HoldingResponse(
        symbol=holding.stock.symbol,
        name=holding.stock.name,
        quantity=holding.quantity,
        average_buy_price=holding.average_buy_price,
        current_market_price=current_price,
        invested_value=invested_value,
        current_value=current_value,
        profit_loss=profit_loss,
        profit_loss_percentage=percentage,
    )


def realized_profit_loss(transactions: list[Transaction]) -> Decimal:
    """Replay the immutable trade ledger using weighted-average cost basis."""
    positions: dict[int, tuple[Decimal, Decimal]] = {}
    realized = Decimal("0")
    for transaction in transactions:
        quantity, average_cost = positions.get(transaction.stock_id, (Decimal("0"), Decimal("0")))
        if transaction.transaction_type == "BUY":
            combined_quantity = quantity + transaction.quantity
            average_cost = (
                (quantity * average_cost + transaction.total_amount) / combined_quantity
            )
            positions[transaction.stock_id] = (combined_quantity, average_cost)
        elif transaction.transaction_type == "SELL":
            # Valid orders cannot exceed the owned quantity; this guard prevents
            # corrupted legacy data from silently producing a false P/L result.
            if transaction.quantity > quantity:
                raise ValueError("Transaction ledger contains an oversell")
            realized += money(transaction.total_amount - average_cost * transaction.quantity)
            positions[transaction.stock_id] = (quantity - transaction.quantity, average_cost)
    return money(realized)
