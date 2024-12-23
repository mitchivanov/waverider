def main():
    
    asset_a_funds = float(input("Enter asset a funds: "))
    asset_b_funds = float(input("Enter asset b funds: "))
    current_price = float(input("Enter current price: "))
    grids = int(input("Enter grids: "))
    deviation = float(input("Enter deviation: "))

    # 1) Общая стоимость
    total_value = asset_b_funds * current_price + asset_a_funds

    # 2) Желаемое конечное количество апельсинов (asset_b)
    final_oranges = total_value / (2 * current_price)  # x

    # 3) Сколько апельсинов нужно купить/продать
    delta_oranges = final_oranges - asset_b_funds

    # Если нужно купить апельсины (delta_oranges > 0),
    # то нам понадобятся доллары. Проверим, есть ли они:
    if delta_oranges > 0:
        # Проверяем, хватает ли долларов
        required_dollars = delta_oranges * current_price
        if required_dollars > asset_a_funds:
            print(
                "Не хватает долларов для покупки нужного числа апельсинов."
            )
            # Либо ограничиваемся тем, что можем купить
            delta_oranges = asset_a_funds / current_price

    # Аналогично, если нужно продать (delta_oranges < 0),
    # проверяем, есть ли апельсины:
    elif delta_oranges < 0:
        if abs(delta_oranges) > asset_b_funds:
            print(
                "Не хватает апельсинов для продажи нужного количества."
            )
            # Либо ограничиваемся тем, что можем продать
            delta_oranges = -asset_b_funds

    # 4) Раскладываем delta_oranges на «n» уровней сетки
    delta_per_grid = delta_oranges / grids if grids else delta_oranges

    # Поскольку «сеточная» торговля предполагает, что мы ставим ордера
    # на разных ценовых уровнях, определим шаг цены.
    # Допустим, мы равномерно ставим цены от min_price до max_price.
    # Если покупаем (delta > 0), логично ставить уровень выше текущего.
    # Но если хотим ловить движение рынка, можно «распылить»:
    # от текущей цены до внешнего курса (или чуть выше).
    if delta_oranges > 0:
        min_price = current_price
        max_price = current_price * (1 + deviation)
    else:
        # Если продаём, то наоборот: от текущей цены до чуть ниже
        min_price = current_price * (1 - deviation)
        max_price = current_price

    price_step = (max_price - min_price) / grids if grids else 0

    # В этих списках будут накоплены объёмы для покупки/продажи на каждом уровне
    grid_buy_amounts = []
    grid_sell_amounts = []

    # 5) Формируем списки заявок по уровням
    current_level_price = min_price
    for i in range(grids):
        current_level_price = min_price + price_step * i

        if delta_oranges > 0:
            # Покупка на каждом уровне
            grid_buy_amounts.append(delta_per_grid)
            grid_sell_amounts.append(0)
        else:
            # Продажа
            grid_buy_amounts.append(0)
            grid_sell_amounts.append(delta_per_grid)

    print(
        f"Рассчитаны сеточные ордера для балансировки:\n"
        f"  Текущая цена: {current_price}\n"
        f"  Итоговое количество апельсинов (цель): {final_oranges:.6f}\n"
        f"  Изменение (delta) апельсинов: {delta_oranges:.6f}\n"
        f"  Общее количество уровней: {grids}\n"
        f"  Пример цены первого уровня: {min_price}\n"
        f"  Пример цены последнего уровня: {max_price}\n"
        f"  Количество апельсинов на уровень: {delta_per_grid}\n"
    )
    
if __name__ == "__main__":
    main()
