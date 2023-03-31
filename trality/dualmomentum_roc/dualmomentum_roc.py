"""
Inspired by https://oxfordstrat.com/trading-strategies/dual-momentum-rate-of-change/
"""
import datetime
import numpy as np
import pandas as pd

SYMBOL = "BTCUSDT"

FastMA_Length = 2
SlowMA_Length = 30

ATR_Length = 20
ATR_Stop = 2  # 6


DATE_END_OF_BACKTEST: pd.Timestamp = pd.to_datetime("2023/03/31").date()


def cancel_pending_orders():
    for order in query_open_orders():
        if order.status == OrderStatus.Pending:
            cancel_order(order.id)


@enable_margin_trading()
@parameter(name="time_index", type="int", default=1, min=1, max=141, enabled=True)
@parameter(name="Look_Back_1", type="int", default=30, min=20, max=200, enabled=True)
def initialize(state, params):
    state.number_offset_trades = 0
    state.exits = {"StopLossExit": 0, "TimeExit": 0}

@schedule(interval="1d", symbol=SYMBOL)
def handler(state, data, params):
    if data is None:
        print("data is None")
        return
    now: pd.Timestamp = pd.to_datetime(data.last_time, unit="ms")
    today = now.date()

    current_price = data.close_last

    Look_Back_1 = params.Look_Back_1 # 90 # [20, 200], Step = 5
    Look_Back_2 = round(Look_Back_1 * 0.5)


    OpenLongTrade = False
    OpenShortTrade = False

    roc1 = data.roc(period=Look_Back_1, select="close")
    roc2 = data.roc(period=Look_Back_2, select="close")

    if roc1 is None or roc2 is None:
        return

    if roc1[-1] > 0 and roc2[-1] > 1:
        OpenLongTrade = True
    
    elif roc1[-1] < 0 and roc2[-1] < 1:
        OpenShortTrade = True

    portfolio = query_portfolio()
    balance_quoted = portfolio.excess_liquidity_quoted
    buy_value = float(balance_quoted) * 0.99

    position: TralityPosition = query_open_position_by_symbol(
        data.symbol, include_dust=False
    )
    has_position = position is not None

    order = None
    if not has_position:
        if OpenLongTrade or OpenShortTrade:
            state.entry_date = now

        if OpenLongTrade:
            cancel_pending_orders()
            state.order_exit = None
            order: TralityMarginOrder = margin_order_market_value(symbol=data.symbol, value=buy_value) # creating market order
            #target = 1
            #margin_order_market_target(data.symbol, target)
        elif OpenShortTrade:
            cancel_pending_orders()
            state.order_exit = None
            order: TralityMarginOrder = margin_order_market_value(symbol=data.symbol, value=-buy_value) # creating market order
            #target = -1
            #margin_order_market_target(data.symbol, target)

    StopLossExit = False

    # refresh order_exit to see if it was triggered
    if state.order_exit is not None:
        state.order_exit.refresh()
        if state.order_exit.is_filled():
            state.exits["StopLossExit"] += 1
            margin_close_position(symbol=data.symbol)
            state.order_exit = None

    if (OpenLongTrade or OpenShortTrade) and order is not None:
        # direction = np.sign(position.exposure)
        if OpenLongTrade:
            direction = 1
        elif OpenShortTrade:
            direction = -1

        # StopLossExit
        atr = data.atr(ATR_Length).last[-1]
        #amount = abs(float(position.exposure))
        amount = abs(order.quantity)
        order_qty = subtract_order_fees(amount) * (-direction)
        # entry = float(position.average_price)
        entry = current_price
        if direction > 0:  # Long
            # Long Trades: A sell stop is placed at [Entry − ATR(ATR_Length) * ATR_Stop].
            price_SL = entry - atr * ATR_Stop
            print(entry, price_SL)
            state.order_exit = margin_order_iftouched_market_amount(
                symbol=data.symbol, amount=order_qty, stop_price=price_SL
            )
        else:
            # Short Trades: A buy stop is placed at [Entry + ATR(ATR_Length) * ATR_Stop].
            price_SL = entry + atr * ATR_Stop
            print(entry, price_SL)
            state.order_exit = margin_order_iftouched_market_amount(
                symbol=data.symbol, amount=order_qty, stop_price=price_SL
            )

    TimeExit = False
    if has_position:
        # TimeExit
        if now >= state.entry_date + datetime.timedelta(days=params.time_index):
            TimeExit = True
            state.exits["TimeExit"] += 1


    if has_position and TimeExit:
        # print("close position")
        margin_close_position(data.symbol)  # closing position

    """
    5) Check strategy profitability
        > print information profitability on every offsetting trade
    """
    if state.number_offset_trades < portfolio.number_of_offsetting_trades:
        pnl = query_portfolio_pnl()
        print("-------")
        print("Accumulated Pnl of Strategy: {}".format(pnl))

        offset_trades = portfolio.number_of_offsetting_trades
        number_winners = portfolio.number_of_winning_trades
        number_losers = offset_trades - number_winners
        print("Number of winning trades {}/{}.".format(number_winners, offset_trades))
        print("Number of losing trades {}/{}.".format(number_losers, offset_trades))
        print("Best trade Return : {:.2%}".format(portfolio.best_trade_return))
        print("Worst trade Return : {:.2%}".format(portfolio.worst_trade_return))
        print(
            "Average Profit per Winning Trade : {:.2f}".format(
                portfolio.average_profit_per_winning_trade
            )
        )
        print(
            "Average Loss per Losing Trade : {:.2f}".format(
                portfolio.average_loss_per_losing_trade
            )
        )
        expected_value = (
            float(portfolio.average_profit_per_winning_trade) * number_winners
        ) / offset_trades + (
            float(portfolio.average_loss_per_losing_trade) * number_losers
        ) / offset_trades
        print("Expected_value : {:.2f}".format(expected_value))
        # reset number offset trades
        state.number_offset_trades = portfolio.number_of_offsetting_trades
    if today == DATE_END_OF_BACKTEST:
        print("end of backtest")
        print("exits: ", state["exits"])
