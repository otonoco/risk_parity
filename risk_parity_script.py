# -*- coding: utf-8 -*-
"""“Invest Tools.ipynb”

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1MmpBpnj_EpSpNTPrwtd4EoRfY8mCjqeI

This colab interactive notebook is a open source tool. It contains two parts:
 1. Adaptive Risk Parity Tool based on Inverse volatility. For details, you can check this two links: [Adaptive Risk Parity 投资策略](https://www.physixfan.com/risk-parity-touziceluegaijinbandongtaidiaozhenguprohetmfdebili/) and [Risk Parity 的具体含义，以及与 Inverse Volatility 的区别与联系](https://www.physixfan.com/risk-parity-dejutihanyijiyu-inverse-volatility-dequbie/)
 2. Portfolio Rebalance Helper. It's a tool helps you to convert your current portfolio pie to target pie.
---
# To use this notebook, click the `Copy to Drive` Button on top to copy it to your google driver and run, otherwise, google won't assgin a runtime to you.

---
 Credit: 
 1. **Inverse volatility**: Zebing Lin (https://github.com/linzebing)
 2. **Rest part of the notebook**:  2b-bro
"""

#!/usr/local/bin/python3
# Original Author: Zebing Lin (https://github.com/linzebing)
# Rewriter & maintainer: Kyon Smith 
#@markdown ####*← Step1. Click the Play button to initiate funtions for this notebook.*
from datetime import datetime, date
#import math
import numpy as np
import time
import sys
import requests
import logging
from bs4 import BeautifulSoup

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36"}

def get_stock_rt_price(symbol):
    url = f'https://finance.yahoo.com/quote/{symbol}' 
    r = requests.get(url)
    content = BeautifulSoup(r.content, 'lxml')
    print(content)
    price = price = content.find("fin-streamer",attrs={"data-reactid":47}).text
    try:
        price = float(price.replace(',', ''))
    except ValueError as e:
        logging.error(e)
        return
    return price

def get_volatility_and_performance(symbol, end_timestamp, window_size = 20):
    num_trading_days_per_year = 252
    date_format = "%Y-%m-%d"
    #end_timestamp = int(time.time())
    start_timestamp = int(end_timestamp - (1.4 * (window_size + 1) + 4) * 86400)
    download_url = f"https://query1.finance.yahoo.com/v7/finance/download/{symbol}"
    res = requests.get(download_url, headers = headers, params = {"period1":start_timestamp,
                                            "period2": end_timestamp,
                                            "interval": "1d",
                                            "events": "history"
                                             })
    lines = res.text.strip().split('\n')
    #print(lines)
    assert lines[0].split(',')[0] == 'Date'
    assert lines[0].split(',')[5] == 'Adj Close'
   
    prices = []
    for line in lines[1:]:
        prices.append(float(line.split(',')[5]))
    volatilities_in_window = []
    prices.reverse()
    for i in range(window_size):
        volatilities_in_window.append(np.log(prices[i] / prices[i + 1]))  
        
    most_recent_date = datetime.strptime(lines[-1].split(',')[0], date_format).date()
    assert (datetime.fromtimestamp(end_timestamp).date() - most_recent_date).days <= 4, "today is {}, most recent trading day is {}".format(date.today(), most_recent_date)

    return {"symbol":symbol,
            "volatility":np.std(volatilities_in_window, ddof = 1) * np.sqrt(num_trading_days_per_year), 
            "performance":prices[0] / prices[window_size] - 1.0}

def get_inverse_volatility_allocation(symbols,end_timestamp,window_size=20):
    volatilities = []
    performances = []
    sum_inverse_volatility = 0.0
    for symbol in symbols:
        _ , volatility, performance = get_volatility_and_performance(symbol, end_timestamp, window_size).values()
        sum_inverse_volatility += 1 / volatility
        volatilities.append(volatility)
        performances.append(performance)

    print ("Portfolio: {}, as of {} (window size is {} days)".format(str(symbols), datetime.fromtimestamp(end_timestamp).strftime('%Y-%m-%d'), window_size))
    allocations = [float(1 / (volatility * sum_inverse_volatility)) for volatility in volatilities]
    return [{"symbol":symbol,
             "allocation":allocation,
             "annualized_volatility":volatility
             ,"performance":performance} for symbol,allocation,volatility,performance in zip(symbols,allocations,volatilities,performances)]

def rebalance_pie(current_share_pie, target_pie, fractional_share = False):
    # get all stock symbols
    current_stocks = set(current_share_pie.keys())
    target_stocks = set(target_pie.keys())
    current_stocks.remove("USD_CASH")

    # get unique symbols in each pie
    stock_symbols = set(current_stocks).union(target_stocks)
    unique_current = set(current_stocks).difference(target_stocks)
    unique_target = set(target_stocks).difference(current_stocks)
    
    # add unique symbols to pies to avoid KeyError
    current_share_pie.update(dict(zip(unique_target,[0] * len(unique_target))))
    target_pie.update(dict(zip(unique_current,[0] * len(unique_current))))

    # get stock real time price
    stock_prices = {symbol:get_stock_rt_price(symbol) for symbol in stock_symbols}

    # calculate the whole vaule of currrent pie
    whole_value = 0
    for symbol,share in current_share_pie.items():
        if symbol != "USD_CASH":
            whole_value += share * stock_prices[symbol]
        else:
            whole_value += share
    # get target pie of shares
    if fractional_share:
        target_share_pie = {symbol: whole_value * allocation / stock_prices[symbol] for symbol, allocation in target_pie.items()}
    else:
        target_share_pie = {symbol: round(whole_value * allocation / stock_prices[symbol]) for symbol, allocation in target_pie.items()}
    # print how to modify current pie to target pie
    for symbol in stock_symbols:
        delta = target_share_pie[symbol] - current_share_pie[symbol]
        if delta > 0:
            print(f"Buy {delta} shares of {symbol} at {stock_prices[symbol]}")
        elif delta < 0:
            print(f"Sell {abs(delta)} shares of {symbol} at {stock_prices[symbol]}")
    # return details of target pie
    return [{"symbol":symbol,
            "share":share,
            "market_value":stock_prices[symbol] * share,
            "allocation":target_pie[symbol]} for symbol, share in target_share_pie.items() if share != 0]

#@markdown #### *← When finish filling the form, Click the Play button to run the cell.*
#@markdown ## **Adaptive Risk Parity Tool** ##
#@markdown Calculate the share ratio based on inverse volatility of input symbols below:

#@markdown ---
end_timestamp = "2021-07-01" #@param {type:"date"}
end_timestamp = int(datetime.timestamp(datetime.strptime(end_timestamp,'%Y-%m-%d')))
#@markdown **window_size** is the trading days you want to calculate for volatilty, default 20 days (one month).
window_size = 20 #@param {type:"slider", min:0, max:100, step:1}
#@markdown **portfolio** is a python list of your portfolio for calcuate share ratio based on inverse volatilty. 
#@markdown Format: ["STOCK_A","STOCK_B","STOCK_C"]
portfolio =  ["UPRO","TMF"] #@param {type:"raw")

result = get_inverse_volatility_allocation(portfolio,end_timestamp,window_size)

for stock in result:
    print (f'{stock["symbol"]} allocation ratio: {stock["allocation"] * 100:.2f}% (anualized volatility: {stock["annualized_volatility"] * 100:.2f}%, performance: {stock["performance"] * 100:.2f}%)')

risk_parity_pie = {stock["symbol"]: stock["allocation"] for stock in result}



#@markdown #### *← When finish filling the form, Click the Play button to run the cell.*
#@markdown ## **Portfolio Rebalance Helper**
#@markdown ---
#@markdown **current_pie** is a python dictionary of your current portfolio.

#@markdown Format: {"STOCK_A":Shares of A,"STOCK_B":Shares of B,"STOCK_C":Shares of C,"USD_CASH":Current Cash Value}
current_pie =  {"UPRO": 10, "TMF": 10, "USD_CASH": 500} #@param {type:"raw")

#@markdown check the box below if you want to use the pie calcualted by last cell. Otherwise, uncheck the box and put your **target_pie** below.
use_risk_parity_pie =True #@param {type:"boolean"}

#@markdown *Optional*: **target_pie** your target allocation pie, a python dictionary.

#@markdown Format: {"STOCK_A":ratio of A, "STOCK_B":ratio of B, "STOCK_C":ratio of C}
target_pie =  {"SPY": 0.5 , "TLT": 0.5 } #@param {type:"raw")

#@markdown check the box below if your broker support fractional share.
fractional_share = False #@param {type:"boolean"}

if use_risk_parity_pie:
    target_pie = risk_parity_pie

target_pie_details = rebalance_pie(current_pie, target_pie, fractional_share)

print("\nThis is your final target pie:")

for stock in target_pie_details:
    print (f'{stock["symbol"]} share: {stock["share"]}, market value: {stock["market_value"]}, allocation ratio: {stock["allocation"] * 100:.2f}')

