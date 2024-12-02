export const binanceService = {
  async getExchangeInfo() {
    const response = await fetch('https://api.binance.com/api/v3/exchangeInfo');
    const data = await response.json();
    return data;
  },

  // Получаем уникальные базовые и котируемые валюты
  parseExchangeInfo(data: any) {
    const baseAssets = new Set<string>();
    const quoteAssets = new Set<string>();

    data.symbols.forEach((symbol: any) => {
      if (symbol.status === 'TRADING') {
        baseAssets.add(symbol.baseAsset);
        quoteAssets.add(symbol.quoteAsset);
      }
    });

    return {
      baseAssets: Array.from(baseAssets).sort(),
      quoteAssets: Array.from(quoteAssets).sort()
    };
  }
};
