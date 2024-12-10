from sellbot_strategy import SellBot

if __name__ == "__main__":
    # Конфигурация
    api_key = '55euYhdLmx17qhTB1KhBSbrsS3A79bYU0C408VHMYsTTMcsyfSMboJ1d1uEWNLq3'
    api_secret = '2zlWvVVQIrj5ZryMNCkt9KIqowlQQMdG0bcV4g4LAinOnF8lc7O3Udumn6rIAyLb'
    
    # Параметры торговли
    min_price = 90000
    max_price = 110000
    num_levels = 10
    reset_threshold_pct = 2.0
    pair = "BTCUSDT"
    batch_size = 0.001

    # Создание и запуск бота
    bot = SellBot(
        api_key=api_key,
        api_secret=api_secret,
        min_price=min_price,
        max_price=max_price,
        num_levels=num_levels,
        reset_threshold_pct=reset_threshold_pct,
        pair=pair,
        batch_size=batch_size
    )
    
    # Запуск основного цикла бота
    bot.run()