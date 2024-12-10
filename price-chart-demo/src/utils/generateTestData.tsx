interface PriceData {
    time: string;
    value: number;
  }
  
  interface Order {
    price: number;
    type: 'buy' | 'sell';
    openTime: string;
    closeTime: string;
  }
  
  export const generatePriceData = (days: number = 30): PriceData[] => {
    const data: PriceData[] = [];
    const basePrice = 65000;
    const now = new Date();
  
    for (let i = days; i >= 0; i--) {
      const date = new Date(now);
      date.setDate(date.getDate() - i);
      
      // Генерируем случайное изменение цены в пределах ±2%
      const randomChange = basePrice * (Math.random() * 0.04 - 0.02);
      const price = basePrice + randomChange * (i + 1);
  
      data.push({
        time: date.toISOString().split('T')[0],
        value: Math.round(price)
      });
    }
  
    return data;
  };
  
  export const generateOrders = (currentPrice: number): Order[] => {
    const orders: Order[] = [];
    const now = new Date();
    
    // Генерируем 3 ордера на покупку ниже текущей цены
    for (let i = 1; i <= 3; i++) {
      const openDate = new Date(now);
      openDate.setDate(openDate.getDate() - Math.floor(Math.random() * 15)); // Случайная дата открытия в последние 15 дней
      
      const closeDate = new Date(openDate);
      closeDate.setDate(closeDate.getDate() + Math.floor(Math.random() * 10) + 1); // Закрытие через 1-10 дней после открытия
      
      orders.push({
        price: Math.round(currentPrice * (1 - 0.01 * i)),
        type: 'buy',
        openTime: openDate.toISOString().split('T')[0],
        closeTime: closeDate.toISOString().split('T')[0]
      });
    }
  
    // Генерируем 3 ордера на продажу выше текущей цены
    for (let i = 1; i <= 3; i++) {
      const openDate = new Date(now);
      openDate.setDate(openDate.getDate() - Math.floor(Math.random() * 15));
      
      const closeDate = new Date(openDate);
      closeDate.setDate(closeDate.getDate() + Math.floor(Math.random() * 10) + 1);
      
      orders.push({
        price: Math.round(currentPrice * (1 + 0.01 * i)),
        type: 'sell',
        openTime: openDate.toISOString().split('T')[0],
        closeTime: closeDate.toISOString().split('T')[0]
      });
    }
  
    return orders;
  };