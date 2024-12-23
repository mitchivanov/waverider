import asyncio
import logging
import datetime
import aiohttp
from app.strategies.gridstrat import GridStrategy
from app.database import async_session
from sqlalchemy import delete
from app.models.models import ActiveOrder
from app.strategies.logger import AsyncLogger


class IndexFundStrategy(GridStrategy):
    """
    Индексный фонд: контролирует внутренний курс (соотношение двух активов),
    сравнивая его с 'внешним' курсом. При превышении порога девиации
    останавливает грид-стратегию, перераспределяет и запускает заново.
    """

    def __init__(
        self,
        bot_id,
        symbol,
        api_key,
        api_secret,
        testnet,
        asset_a_funds,
        asset_b_funds,
        grids,
        deviation_threshold,
        growth_factor,
        use_granular_distribution,
        trail_price=True,
        only_profitable_trades=False,
        index_deviation_threshold=0.01,
    ):
        super().__init__(
            bot_id=bot_id,
            symbol=symbol,
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
            asset_a_funds=asset_a_funds,
            asset_b_funds=asset_b_funds,
            grids=grids,
            deviation_threshold=deviation_threshold,
            growth_factor=growth_factor,
            use_granular_distribution=use_granular_distribution,
            trail_price=trail_price,
            only_profitable_trades=only_profitable_trades
        )
        # Порог для сравнения «внешнего» курса (рыночного) и «внутреннего» (пропорция активов)
        self.index_deviation_threshold = index_deviation_threshold

        # Сохраняем «внутреннее» соотношение активов при старте
        self.internal_ratio = self._calculate_internal_ratio()
        
        self.trades_logger = AsyncLogger(bot_id)

        # Запускаем отдельную задачу по контролю «индексного» фонда
        asyncio.create_task(self.index_control_loop())

    async def _calculate_internal_ratio(self):
        """
        Считаем внутреннее соотношение (курс) как отношение asset_b_funds к asset_a_funds.
        Примерно говоря, если asset_a_funds – это «количество USDT», а asset_b_funds – «количество BTC»,
        то self.internal_ratio ~ (BTC / USDT).
        """
        if self.asset_a_funds or self.asset_b_funds == 0:
            await self.trades_logger.fatal(f"Asset a or asset b is 0. Internal ratio is not calculated.")
        return self.asset_b_funds / self.asset_a_funds

    async def calculate_index_fund_order_size(self):
        """
        Рассчитывает размер ордеров для стратегии индексного фонда.
        Размеры подбираются так, чтобы при срабатывании всех ордеров
        внутреннее соотношение активов изменилось пропорционально
        допустимому отклонению цены.
        """
        if self.current_price is None:
            ticker = self.binance_client.client.get_ticker(symbol=self.symbol)
            self.current_price = float(ticker['lastPrice'])
        
        # Рассчитываем целевые соотношения при достижении пределов отклонения
        target_ratio_low = self.internal_ratio * (1 - self.index_deviation_threshold)
        target_ratio_high = self.internal_ratio * (1 + self.index_deviation_threshold)
        
        # Рассчитываем необходимое количество asset_b для достижения целевых соотношений
        # при текущем количестве asset_a
        target_asset_b_low = self.asset_a_funds * target_ratio_low
        target_asset_b_high = self.asset_a_funds * target_ratio_high
        
        # Разница между текущим и целевым количеством asset_b
        delta_b_low = self.asset_b_funds - target_asset_b_low
        delta_b_high = target_asset_b_high - self.asset_b_funds
        
        # Распределяем разницу между гридами
        self.buy_order_sizes = [delta_b_low / self.grids] * self.grids
        self.sell_order_sizes = [delta_b_high / self.grids] * self.grids
        
        await self.trades_logger.log(
            f"Calculated order sizes: buy={self.buy_order_sizes[0]}, "
            f"sell={self.sell_order_sizes[0]} per grid"
        )

    async def execute_strategy(self):
        """Execute the index fund strategy with continuous monitoring."""
        logging.info("Starting the index fund strategy execution.")
        
        price_update_task = None

        
        try:
            # Создаем одну сессию на все время работы стратегии
            self.session = aiohttp.ClientSession()
            price_update_task = asyncio.create_task(self.update_price())
            
            last_checked_price = None  # Track the last checked price
            
            while not self.stop_flag:
                
                # Ensure the current price is updated
                if self.current_price is not None and self.current_price != last_checked_price:
                    last_checked_price = self.current_price

                    if self.initial_price is None:
                        
                        # Step 1: Set initial price
                        self.initial_price = self.current_price
                        await self.trades_logger.log(f"Initial price set to ${self.initial_price}. Calculating grid levels and order sizes.")
                        
                        # Step 2: Calculate grid levels first
                        await self.trades_logger.log(f"Calculating grid levels based on the current price and deviation threshold.")
                        await self.calculate_grid_levels(self.initial_price)
                        
                        # Step 3: Then calculate order sizes
                        await self.trades_logger.log(f"Calculating order sizes based on the current price and deviation threshold.")
                        await self.calculate_index_fund_order_size()
                        
                        # Step 4: Place initial orders
                        await self.trades_logger.log(f"Placing initial orders based on the grid levels and order sizes.")
                        await self.place_batch_orders()
                    
                    # Periodically calculate the deviation from the initial price
                    deviation = (self.current_price - self.initial_price) / self.initial_price
                    self.deviation = deviation
                    
                    await self.trades_logger.log(f"Deviation from initial price: {deviation}")

                    # Define tasks for checking buy and sell orders
                    await asyncio.gather(self.check_initial_buy_orders(), self.check_initial_sell_orders())
                                        
                    # Check open trades
                    await self.check_open_trades()

                    # Log summary of the checks
                    await self.trades_logger.log(f"Summary: {len(self.buy_positions)} buy orders and {len(self.sell_positions)} sell orders checked.")

                    # Reset grid if deviation threshold is reached
                    if abs(deviation) >= self.deviation_threshold:
                        logging.info("Deviation threshold reached. Resetting grid.")
                        await self.rebalance_and_restart(self.current_price)

                # Sleep asynchronously to wait before the next price check
                await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"Error in strategy execution: {str(e)}")
        finally:
            # Закрываем сессии только при завершении стратегии
            if price_update_task:
                await price_update_task
            await self.stop_strategy()

    async def rebalance_and_restart(self, external_ratio):
        """
        Сбрасываем ордера и выставляем новое соотношение активов
        (подгоняем internal_ratio к внешнему), затем заново запускаем грид.
        """
        
        await self.cancel_all_orders(self.bot_id, "all")
        
        self.asset_a_funds += self.realized_profit_a
        self.asset_b_funds += self.realized_profit_b

        self.internal_ratio = self._calculate_internal_ratio()
        
        self.initial_price = self.current_price

        await self.calculate_grid_levels(self.initial_price)
        
        await self.calculate_index_fund_order_size()

        
        
        
async def start_index_fund_strategy(parameters: dict) -> IndexFundStrategy:
    """
    Создат и запускает экземпляр торговой стратегии.
    
    Args:
        parameters (dict): Параметры для инициализации стратегии
        
    Returns:
        GridStrategy: Запущенный экземпляр стратегии
    """
    try:
        strategy = IndexFundStrategy(**parameters)
        asyncio.create_task(strategy.execute_index_fund_strategy())
        return strategy
    except Exception as e:
        logging.error(f"Ошибка при запуске index-fund-стратегии: {e}")
        raise

async def stop_index_fund_strategy(strategy: IndexFundStrategy) -> bool:
    """
    Останавливает работающую стратегию.
    
    Args:
        strategy (GridStrategy): Экземпляр работающей стратегии
        
    Returns:
        bool: True если остановка прошла успешно
    """
    try:
        strategy.stop_flag = True
        await strategy.close_all_sessions()
        await strategy.trades_logger.close()
        logging.info("Index fund strategy stopped successfully")
        return True
    except Exception as e:
        logging.error(f"Ошибка при остановке index-fund-стратегии: {e}")
        raise
