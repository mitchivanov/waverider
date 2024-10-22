import asyncio
import logging
from gridstrat import GridStrategy

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set the logging level to INFO to reduce verbosity
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Output logs to the console
    ]
)

# Suppress debug messages from specific libraries
logging.getLogger('websockets').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('aiohttp').setLevel(logging.WARNING)

async def main():
    # Define trading parameters
    symbol = 'ETHUSDT'
    asset_a_funds = 1000  # Example funds in USDT (Asset A)
    asset_b_funds = 0.5  # Example funds in BTC (Asset B)
    grids = 10  # Number of grid levels
    deviation_threshold = 0.004  # 0.02 is 2% deviation
    growth_factor = 0.5  # Example growth factor
    use_granular_distribution = True  # Use granular distribution
    trail_price = True  # Whether to trail the price or not
    only_profitable_trades = False  # Whether to only execute profitable trades

    # Initialize the grid strategy
    strategy = GridStrategy(
        symbol=symbol,
        asset_a_funds=asset_a_funds,
        asset_b_funds=asset_b_funds,
        grids=grids,
        deviation_threshold=deviation_threshold,
        growth_factor=growth_factor,  # Pass the growth factor
        use_granular_distribution=use_granular_distribution,  # Pass the granular distribution flag
        trail_price=trail_price,
        only_profitable_trades=only_profitable_trades
    )

    # Execute the strategy
    try:
        await strategy.execute_strategy()
    except Exception as e:
        logging.error(f"An error occurred: {e}")
    finally:
        await strategy.session.close()  # Ensure the session is closed

if __name__ == "__main__":
    asyncio.run(main())
