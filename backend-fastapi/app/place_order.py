from binance_client import BinanceClient
import asyncio

async def main():
    binance_client = BinanceClient(api_key='55euYhdLmx17qhTB1KhBSbrsS3A79bYU0C408VHMYsTTMcsyfSMboJ1d1uEWNLq3', 
                                  api_secret='2zlWvVVQIrj5ZryMNCkt9KIqowlQQMdG0bcV4g4LAinOnF8lc7O3Udumn6rIAyLb', 
                                  testnet=True)
    
    try:
        order = await binance_client.place_order_async('BTCUSDT', 'SELL', 0.1, 80000, 'LIMIT')
        print(order)
    finally:
        await binance_client.close()

if __name__ == "__main__":
    asyncio.run(main())