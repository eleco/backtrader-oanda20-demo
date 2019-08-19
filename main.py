from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import argparse
import datetime
import math
import backtrader as bt
from backtrader.utils import flushfile  
import btoandav20

StoreCls = btoandav20.stores.OandaV20Store
DataCls = btoandav20.feeds.OandaV20Data
# BrokerCls = btoandav20.brokers.OandaV20Broker

# Create a Stratey
class MA_CrossOver(bt.SignalStrategy):
    alias = ('SMA_CrossOver',)

    params = (
        # period for the fast Moving Average
        ('pfast', 5),
        # period for the slow moving average
        ('pslow', 60)
    )

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(), txt))   

    def notify_data(self, data, status, *args, **kwargs):
        print('*' * 5, 'DATA NOTIF:', data._getstatusname(status), *args)

    def notify_store(self, msg, *args, **kwargs):
        print('*' * 5, 'STORE NOTIF:', msg)
 
    
    def __init__(self):
        # Keep a reference to the "close" line in the data[0] dataseries
        self.dataclose = self.datas[0].close

        # To keep track of pending orders and buy price/commission
        self.order = None
        self.buyprice = None
        self.buycomm = None
        
        # Indicators
        sma1, sma2 = bt.ind.SMA(period=self.p.pfast), bt.ind.SMA(period=self.p.pslow)
        self.signal_add(bt.SIGNAL_LONGSHORT, bt.ind.CrossOver(sma1, sma2))
        
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return

        # Check if an order has been completed
        # Attention: broker could reject order if not enough cash
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    'BUY EXECUTED, Price: %.5f, Cost: %.5f, Comm %.5f' %
                    (order.executed.price,
                     order.executed.value,
                     order.executed.comm))

                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            else:  # Sell
                self.log('SELL EXECUTED, Price: %.5f, Cost: %.5f, Comm %.5f' %
                         (order.executed.price,
                          order.executed.value,
                          order.executed.comm))

            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return

        self.log('GROSS %.5f, NET %.5f' %
                 (trade.pnl, trade.pnlcomm))        
        
    def next(self):
        self.log('Date: %s, Close, %.5f' % (self.data.datetime.datetime(),self.dataclose[0]))

        # Check if an order is pending ... if yes, we cannot send a 2nd one
        if self.order:
            return            

class maxRiskSizer(bt.Sizer):
    params = (('risk', 0.99),)

    def __init__(self):
        if self.p.risk > 1 or self.p.risk < 0:
            raise ValueError('The risk parameter is a percentage which must be entered as a float. e.g. 0.5')
        
    def _getsizing(self, comminfo, cash, data, isbuy):
        position = self.broker.getposition(data)
        if not position:
            size = math.floor((cash * self.p.risk) /data.close[0])
        else:
            size = position.size
        return size
            
if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--token', help='Oanda API token')
    parser.add_argument('--account', help='Oanda API account')
    args = parser.parse_args()

    print('token:', args.token)
    print('acct:', args.account)

    # Create a cerebro entity
    cerebro = bt.Cerebro()

    
    # Add a strategy
    cerebro.addstrategy(MA_CrossOver)

    # instantiate data

    #cerebro.broker = oandastore.getbroker()

    oandastore = StoreCls(token = args.token, account = args.account, practice=True)
    
    data = oandastore.getdata(dataname='EUR_USD', 
                       compression=15,
                       backfill=False,
                       fromdate=datetime.datetime(2019, 8, 10),
                       todate=datetime.datetime(2019, 8, 19),
                       qcheck=0.5,
                       timeframe=bt.TimeFrame.Minutes,
                       backfill_start=False,
                       historical=True)


    # Add the Data Feed to Cerebro
    cerebro.adddata(data)

    #cerebro.resampledata(data, timeframe=bt.TimeFrame.Minutes, compression=15)


    # Set our desired cash start
    cerebro.broker.setcash(30000.0)

    # Add sizer
    cerebro.addsizer(maxRiskSizer)

    # Set the commission
    cerebro.broker.setcommission(commission=0.00035)

    # Add Analyzer
    #Cerebro.addanalyzer(bt.analyzers.Benchmark)
    
    # Print out the starting conditions
    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())

    # Run over everything
    ret =cerebro.run(tradehistory=True)
    
    # Print out the final result
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
    
    # Plot the result
    cerebro.plot()