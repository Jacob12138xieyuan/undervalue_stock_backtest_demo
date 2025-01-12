import pandas as pd
from datetime import datetime

def calculate_forward_returns(stocks_df, date, prices):
    """计算股票的前瞻收益率
    
    Args:
        stocks_df (DataFrame): 包含股票信息的DataFrame
        date (datetime): 计算收益率的起始日期
        prices (DataFrame): 股票价格数据，MultiIndex格式(ticker, PX_LAST)
    
    Returns:
        DataFrame: 添加了以下收益率列的stocks_df:
            - return_1d: 1天收益率
            - return_1w: 1周收益率
            - return_1m: 1月收益率
            - return_3m: 3月收益率
            - return_1y: 1年收益率
    """
    # 定义时间窗口（交易日数量）
    periods = {
        '1d': 1,
        '1w': 5,
        '1m': 21,
        '3m': 63,
        '1y': 252
    }

    # 获取日期索引位置
    date_idx = prices.index.get_loc(date)

    # 为每个时间窗口计算收益率
    for period_name, days in periods.items():
        try:
            if date_idx + days < len(prices.index):
                end_date = prices.index[date_idx + days]
                # 计算收益率
                start_prices = prices.loc[date]
                end_prices = prices.loc[end_date]

                returns = []
                for ticker in stocks_df['ticker']:
                    if (ticker, 'PX_LAST') in start_prices.index and (ticker, 'PX_LAST') in end_prices.index:
                        start_price = start_prices[(ticker, 'PX_LAST')]
                        end_price = end_prices[(ticker, 'PX_LAST')]
                        ret = (end_price - start_price) / start_price
                        returns.append(ret)
                    else:
                        returns.append(None)
                
                stocks_df[f'return_{period_name}'] = returns
            else:
                stocks_df[f'return_{period_name}'] = None
        except Exception as e:
            print(f"计算{period_name}收益率时出错: {str(e)}")
            stocks_df[f'return_{period_name}'] = None
    
    return stocks_df

def process_daily_data(indicator_file, evs_file, operinc_file, price_file):
    """处理每日数据并找出低估股票
    
    Args:
        indicator_file (str): 基础财务指标数据文件路径
        evs_file (str): EV/Sales数据文件路径
        operinc_file (str): 预期营业收入增长率数据文件路径
        price_file (str): 价格数据文件路径
    
    筛选条件:
        价值股:
            1. 市值 > 1000亿美元
            2. Altman Z-score > 4（财务稳健）
            3. 毛利率 > 40%
            4. 当前PE相对5年平均PE < 0.9（相对低估）
            5. 5年平均ROE > 20%（高质量）
        
        成长股:
            1. 市值 > 100亿美元
            2. Altman Z-score > 4（财务稳健）
            3. 毛利率 > 40%
            4. 长期债务/总资产 < 40%（财务杠杆适中）
            5. 当前PS相对5年平均 < 0.8（相对低估）
            6. 预期营业收入增长率 > 20%
            7. 当前EV/Sales相对5年平均 < 0.8
            8. Rule of X > 60（成长性指标）
    
    Returns:
        DataFrame: 包含筛选结果的DataFrame，列包括:
            - date: 日期
            - type: 股票类型（value/growth）
            - ticker: 股票代码
            - price: 当前价格
            - return_*: 各期收益率
            - 其他财务指标
    """
    # 读取数据
    print("读取数据文件...")
    indicators = pd.read_csv(indicator_file, header=[0,1], index_col=0, parse_dates=True)
    evs_data = pd.read_csv(evs_file, header=[0,1], index_col=0, parse_dates=True)
    operinc_data = pd.read_csv(operinc_file, header=[0,1], index_col=0, parse_dates=True)
    prices = pd.read_csv(price_file, header=[0,1], index_col=0, parse_dates=True)
    
    # 初始化结果DataFrame
    results = []
    
    # 处理每个交易日
    for date in indicators.index:
        date_str = date.strftime('%Y-%m-%d')
        print(f"\n处理日期: {date_str}")
        
        try:
            # 获取当天所有股票的数据
            daily_data = indicators.loc[date].unstack()  # 展开多级索引
            daily_data.index.name = 'ticker'
            
            # 添加evs数据
            if date in evs_data.index:
                evs_daily = evs_data.loc[date].unstack()
                daily_data['EVS_5Y_AVG'] = evs_daily
            
            # 添加operinc数据
            if date in operinc_data.index:
                operinc_daily = operinc_data.loc[date].unstack()
                daily_data['OPERINC_GROWTH_EST12M'] = operinc_daily
            
            # 计算相对估值指标
            daily_data["CUR_PEto5yAvg"] = daily_data["PE_RATIO"] / daily_data['FIVE_YR_AVG_PRICE_EARNINGS']     # 当前PE相对5年平均PE
            daily_data["CUR_PSto5yAvg"] = daily_data["PX_TO_SALES_RATIO"] / daily_data['FIVE_YEAR_AVG_PRICE_SALES']   # 当前PS相对5年平均PS
            daily_data["CUR_EVSto5yAvg"] = daily_data["EV_TO_T12M_SALES"] / daily_data['EVS_5Y_AVG']           # 当前EV/S相对5年平均
            daily_data["rule_of_x"] = daily_data["EQY_DPS_GROSS_3YR_GROWTH"] * 2 + daily_data["FREE_CASH_FLOW_YIELD"]  # 成长性指标
            
            # 筛选价值股：大市值、财务稳健、高质量、相对低估
            value_stocks = daily_data[
                (daily_data['CUR_MKT_CAP'] * 1000_000 > 100_000_000_000) &  # 市值>1000亿美元
                (daily_data['ALTMAN_Z_SCORE'] > 4) &                         # 财务稳健
                (daily_data['GROSS_MARGIN'] > 40) &                         # 高毛利率
                (daily_data['CUR_PEto5yAvg'] < 0.9) &                      # PE相对低估
                (daily_data['5YR_AVG_RETURN_ON_EQUITY'] > 20)              # 高ROE
            ]
            
            # 筛选成长股：中等市值、高增长、合理负债、相对低估
            growth_stocks = daily_data[
                (daily_data['CUR_MKT_CAP'] * 1000_000 > 10_000_000_000) &   # 市值>100亿美元
                (daily_data['ALTMAN_Z_SCORE'] > 4) &                         # 财务稳健
                (daily_data['GROSS_MARGIN'] > 40) &                         # 高毛利率
                (daily_data['LT_DEBT_TO_TOT_ASSET'] < 40) &                # 适中的负债水平
                (daily_data['CUR_PSto5yAvg'] < 0.8) &                      # PS相对低估
                (daily_data['OPERINC_GROWTH_EST12M'] > 20) &               # 高预期增长
                (daily_data['CUR_EVSto5yAvg'] < 0.8) &                     # EV/S相对低估
                (daily_data['rule_of_x'] > 60)                             # 高成长性指标
            ]
            
            # 打印当天的低估股票
            value_tickers = value_stocks.index.tolist() if not value_stocks.empty else []
            growth_tickers = growth_stocks.index.tolist() if not growth_stocks.empty else []
            
            if value_tickers or growth_tickers:
                if value_tickers:
                    print("价值股:")
                    print(", ".join(value_tickers))
                if growth_tickers:
                    print("成长股:")
                    print(", ".join(growth_tickers))
            else:
                print("今日没有低估股票")
            
            # 添加筛选结果
            for stocks, stock_type in [(value_stocks, 'value'), (growth_stocks, 'growth')]:
                if not stocks.empty:
                    stocks_df = stocks.copy()
                    stocks_df = stocks_df.reset_index()
                    stocks_df['date'] = date_str
                    stocks_df['type'] = stock_type
                    
                    # 添加当天的价格数据
                    if date in prices.index:
                        stocks_df['price'] = prices.loc[date, (stocks_df['ticker'], 'PX_LAST')].values
                    
                    # 计算前瞻收益率
                    stocks_df = calculate_forward_returns(stocks_df, date, prices)
                    
                    # 排序列：date, type, ticker, price, returns, [其他列]
                    return_cols = [col for col in stocks_df.columns if col.startswith('return_')]
                    other_cols = [col for col in stocks_df.columns 
                                if col not in ['date', 'type', 'ticker', 'price'] + return_cols]
                    cols = ['date', 'type', 'ticker', 'price'] + return_cols + other_cols
                    stocks_df = stocks_df[cols]
                    
                    results.append(stocks_df)
                    
        except Exception as e:
            print(f"处理 {date_str} 数据时出错: {str(e)}")
            continue
    
    # 合并所有结果
    if results:
        final_df = pd.concat(results, ignore_index=True)
        filename = "daily_screening_results.csv"
        final_df.to_csv(filename, index=False)
        print(f"\n结果已保存到 {filename}")
        return final_df
    else:
        print("没有找到符合条件的股票")
        return pd.DataFrame()

if __name__ == "__main__":
    # 使用保存的数据文件
    indicator_file = "indicator_data_20240101_20250111.csv"
    evs_file = "evs_data_20240101_20250111.csv"
    operinc_file = "operinc_data_20240101_20250111.csv"
    price_file = "price_data_20230101_20250111.csv"
    
    df = process_daily_data(indicator_file, evs_file, operinc_file, price_file) 