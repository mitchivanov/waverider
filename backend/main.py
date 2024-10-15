import asyncio
import logging
from gridstrat import GridStrategy

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Suppress urllib3 debug logs
logging.getLogger("urllib3").setLevel(logging.WARNING)

async def main():
    symbol = 'BTCUSDT'
    asset_a_funds = 1000  # Example funds in USDT (Asset A)
    asset_b_funds = 0.1  # Example funds in BTC (Asset B)
    grids = 20  # Number of grid levels
    deviation_threshold = 0.02  # 0.02 is 2% deviation
    trail_price = True  # Whether to trail the price or not
    only_profitable_trades = False  # Whether to only execute profitable trades

    # Initialize the grid strategy
    strategy = GridStrategy(
        symbol=symbol,
        asset_a_funds=asset_a_funds,
        asset_b_funds=asset_b_funds,
        grids=grids,
        deviation_threshold=deviation_threshold,
        trail_price=trail_price,
        only_profitable_trades=only_profitable_trades
    )

    # Calculate order size and grid levels
    await strategy.calculate_order_size()
    current_price = strategy.binance_client.get_current_price(symbol)
    await strategy.calculate_grid_levels(current_price)

    # Place initial batch orders
    await strategy.place_batch_orders()

    # Execute the strategy
    await strategy.execute_strategy()

# Check if there's a running loop
try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# Run the main coroutine
loop.run_until_complete(main())
