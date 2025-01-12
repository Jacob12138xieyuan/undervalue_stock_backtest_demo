"""
股票回测模块

功能：
1. 根据每日低估股票名单进行交易
2. 每只新低估股票买入100万美元
3. 不再低估时全部卖出
4. 计算每日持仓表现

输出指标：
- Hit Ratio：盈利交易占比
- Cumulative Return：组合累计收益率
- Daily PnL：每日盈亏
"""

import pandas as pd
import numpy as np
from datetime import datetime

class PortfolioBacktest:
    def __init__(self, screening_file, price_file, initial_capital=10_000_000):
        """
        初始化回测系统
        
        Args:
            screening_file: 每日低估股票文件
            price_file: 股票价格数据文件
            initial_capital: 初始资金，默认1000万美元
        """
        self.initial_capital = initial_capital
        self.position_size = 1_000_000  # 每只股票投资100万美元
        self.cash = initial_capital     # 添加现金属性
        
        # 读取数据
        self.screening_results = pd.read_csv(screening_file)
        self.prices = pd.read_csv(price_file, header=[0,1], index_col=0, parse_dates=True)
        
        # 初始化组合
        self.positions = {}  # {ticker: {'shares': 数量, 'cost': 成本}}
        self.trades = []     # 记录所有交易
        self.daily_stats = []  # 记录每日统计
        
    def run_backtest(self):
        """运行回测"""
        # 获取所有交易日
        dates = sorted(self.screening_results['date'].unique())
        
        for date in dates:
            try:
                # 获取当天低估的股票
                daily_stocks = self.screening_results[
                    self.screening_results['date'] == date
                ]
                undervalued_stocks = set(daily_stocks['ticker'])
                
                # 检查现有持仓
                for holding_ticker in list(self.positions.keys()):
                    if holding_ticker not in undervalued_stocks:
                        # 股票不再低估，卖出
                        self._sell_stock(holding_ticker, date)
                
                # 检查新的低估股票
                for new_ticker in undervalued_stocks:
                    if new_ticker not in self.positions:
                        # 新低估股票，买入
                        self._buy_stock(new_ticker, date)
                
                # 计算当日持仓市值和收益
                self._calculate_daily_stats(date)
                
            except Exception as e:
                print(f"处理日期 {date} 时出错: {str(e)}")
                continue
        
        # 生成回测报告
        self._generate_report()
    
    def _buy_stock(self, ticker, date):
        """买入股票"""
        try:
            price = self.prices.loc[date, (ticker, 'PX_LAST')]
            shares = self.position_size / price
            
            self.positions[ticker] = {
                'shares': shares,
                'cost': price
            }
            
            # 更新现金
            self.cash -= self.position_size
            
            self.trades.append({
                'date': date,
                'ticker': ticker,
                'action': 'BUY',
                'shares': shares,
                'price': price,
                'value': self.position_size
            })
        except Exception as e:
            print(f"买入 {ticker} 时出错: {str(e)}")
    
    def _sell_stock(self, ticker, date):
        """卖出股票"""
        try:
            position = self.positions[ticker]
            price = self.prices.loc[date, (ticker, 'PX_LAST')]
            value = position['shares'] * price
            pnl = value - (position['shares'] * position['cost'])
            
            # 更新现金
            self.cash += value
            
            self.trades.append({
                'date': date,
                'ticker': ticker,
                'action': 'SELL',
                'shares': position['shares'],
                'price': price,
                'value': value,
                'pnl': pnl
            })
            
            del self.positions[ticker]
        except Exception as e:
            print(f"卖出 {ticker} 时出错: {str(e)}")
    
    def _calculate_daily_stats(self, date):
        """计算每日统计数据"""
        try:
            total_value = 0
            daily_pnl = 0
            
            # 计算所有持仓的市值和收益
            for ticker, position in self.positions.items():
                price = self.prices.loc[date, (ticker, 'PX_LAST')]
                market_value = position['shares'] * price
                position_pnl = market_value - (position['shares'] * position['cost'])
                
                total_value += market_value
                daily_pnl += position_pnl
            
            # 总资产 = 持仓市值 + 现金
            total_assets = total_value + self.cash
            
            # 计算截至当日的胜率
            closed_trades = pd.DataFrame(self.trades)
            if not closed_trades.empty:
                sell_trades = closed_trades[closed_trades['action'] == 'SELL']
                if not sell_trades.empty:
                    winning_trades = len(sell_trades[sell_trades['pnl'] > 0])
                    hit_ratio = winning_trades / len(sell_trades)
                else:
                    hit_ratio = 0
            else:
                hit_ratio = 0
            
            # 记录当日统计
            self.daily_stats.append({
                'date': date,
                'portfolio_value': total_value,
                'cash': self.cash,
                'total_assets': total_assets,
                'daily_pnl': daily_pnl,
                'positions_count': len(self.positions),
                'cumulative_return': (total_assets / self.initial_capital) - 1,
                'hit_ratio': hit_ratio,
                'total_trades': len(closed_trades[closed_trades['action'] == 'SELL']),
                'winning_trades': winning_trades if 'winning_trades' in locals() else 0,
                'holdings': list(self.positions.keys())  # 只记录持仓股票代码
            })
            
        except Exception as e:
            print(f"计算日期 {date} 的统计数据时出错: {str(e)}")
    
    def _generate_report(self):
        """生成回测报告"""
        # 创建交易记录DataFrame
        trades_df = pd.DataFrame(self.trades)
        trades_df['date'] = pd.to_datetime(trades_df['date'])
        
        # 创建每日统计DataFrame
        daily_df = pd.DataFrame(self.daily_stats)
        daily_df['date'] = pd.to_datetime(daily_df['date'])
        daily_df.set_index('date', inplace=True)
        
        # 计算Hit Ratio
        closed_trades = trades_df[trades_df['action'] == 'SELL']
        hit_ratio = len(closed_trades[closed_trades['pnl'] > 0]) / len(closed_trades)
        
        # 保存结果
        trades_df.to_csv('backtest_trades.csv', index=False)
        daily_df.to_csv('backtest_daily_stats.csv')
        
        # 打印摘要
        print("\n=== 回测结果摘要 ===")
        print(f"总交易次数: {len(trades_df)}")
        print(f"Hit Ratio: {hit_ratio:.2%}")
        print(f"累计收益率: {daily_df['cumulative_return'].iloc[-1]:.2%}")
        print(f"最大持仓数: {daily_df['positions_count'].max()}")
        print(f"平均持仓数: {daily_df['positions_count'].mean():.1f}")
        print(f"最终总资产: ${daily_df['total_assets'].iloc[-1]:,.2f}")

if __name__ == "__main__":
    # 运行回测
    backtest = PortfolioBacktest(
        screening_file='daily_screening_results.csv',
        price_file='price_data_20230101_20250111.csv'
    )
    backtest.run_backtest() 