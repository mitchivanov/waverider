from binance.client import Client
import pandas as pd
from datetime import datetime
import logging

def get_trade_history(api_key, api_secret, symbols):
    """
    Получение истории торгов по списку торговых пар и сохранение в Excel
    """
    try:
        # Инициализация клиента
        client = Client(api_key, api_secret, testnet=True)
        
        # Создание пустого DataFrame
        all_trades_df = pd.DataFrame()
        
        # Получение торгов для каждой пары
        for symbol in symbols:
            trades = client.get_my_trades(symbol=symbol)
            if trades:
                df = pd.DataFrame(trades)
                df['symbol'] = symbol  # Добавляем столбец с названием пары
                all_trades_df = pd.concat([all_trades_df, df], ignore_index=True)
        
        if not all_trades_df.empty:
            # Конвертация timestamp в читаемую дату
            all_trades_df['time'] = pd.to_datetime(all_trades_df['time'], unit='ms')
            
            # Переименование колонок
            all_trades_df = all_trades_df.rename(columns={
                'time': 'Дата',
                'symbol': 'Пара',
                'price': 'Цена',
                'qty': 'Количество',
                'quoteQty': 'Сумма',
                'commission': 'Комиссия',
                'commissionAsset': 'Актив комиссии',
                'isBuyer': 'Тип'
            })
            
            # Преобразование типа ордера
            all_trades_df['Тип'] = all_trades_df['Тип'].map({True: 'Покупка', False: 'Продажа'})
            
            # Сохранение в Excel
            filename = f'binance_trades_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            all_trades_df.to_excel(filename, index=False)
            print(f"История торгов сохранена в файл: {filename}")
        else:
            print("Торги не найдены")
            
    except Exception as e:
        print(f"Ошибка: {str(e)}")

# Использование
api_key = '55euYhdLmx17qhTB1KhBSbrsS3A79bYU0C408VHMYsTTMcsyfSMboJ1d1uEWNLq3'
api_secret = '2zlWvVVQIrj5ZryMNCkt9KIqowlQQMdG0bcV4g4LAinOnF8lc7O3Udumn6rIAyLb'
symbols = ['BTCUSDT', 'ETHUSDT']  # Добавьте нужные пары

get_trade_history(api_key, api_secret, symbols)