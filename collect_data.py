import pandas as pd
from datetime import datetime, timedelta
from utils import get_index_members, BQL
from xbbg import blp

def collect_all_data(start_date, end_date):
    """收集所有股票的指标数据和价格数据
    
    Args:
        start_date (datetime): 数据收集开始日期
        end_date (datetime): 数据收集结束日期
    
    生成四个CSV文件:
        1. indicator_data_{start_date}_{end_date}.csv: 基础财务指标数据
        2. evs_data_{start_date}_{end_date}.csv: 5年历史EV/Sales数据
        3. operinc_data_{start_date}_{end_date}.csv: 预期营业收入增长率数据
        4. price_data_{start_date}_{end_date}.csv: 股票价格数据
        
    数据格式:
        - 行索引: 日期
        - 列索引: 两级索引(ticker, indicator)
    """
    print("开始获取指标数据")

    # 获取成分股列表
    index_members = get_index_members()
    ticker_names = index_members["ticker"] + " Equity"

    # 获取工作日历
    calendar_df = blp.bdh('SPX Index', 'PX_LAST', start_date, end_date)
    trading_dates = calendar_df.index

    # 定义需要获取的基础财务指标
    Financial_Indicators = [
        "CUR_MKT_CAP",                    # 当前市值
        "PE_RATIO",                       # 市盈率
        "FIVE_YR_AVG_PRICE_EARNINGS",     # 5年平均PE
        "ALTMAN_Z_SCORE",                 # Altman Z评分（财务健康度）
        "5YR_AVG_RETURN_ON_EQUITY",       # 5年平均ROE
        "PX_TO_SALES_RATIO",              # 市销率
        "FIVE_YEAR_AVG_PRICE_SALES",      # 5年平均PS
        "EV_TO_T12M_SALES",               # 企业价值/销售额
        "FREE_CASH_FLOW_YIELD",           # 自由现金流收益率
        "EQY_DPS_GROSS_3YR_GROWTH"        # 3年股息增长率
    ]

    QFinancial_Indicators = [
        "LT_DEBT_TO_TOT_ASSET",  # 长期债务/总资产
        "GROSS_MARGIN",  # 毛利率
        "OPER_INC_GROWTH"  # 营业收入增长率
    ]

    # 1. 获取基础财务指标
    print("\n获取基础财务指标...")
    all_stocks_data = []
    for ticker in ticker_names:
        print(f"\n处理 {ticker}...")
        try:
            stock_data = pd.DataFrame()

            for indicator in Financial_Indicators:
                data = blp.bdh(ticker, indicator, start_date, end_date)
                stock_data = pd.concat([stock_data, data], axis=1)

            for indicator in QFinancial_Indicators:
                qdata = blp.bdh(ticker, indicator, start_date, end_date, fund_per='Q')
                stock_data = pd.concat([stock_data, qdata], axis=1)

            # 处理数据
            non_mkt_cap_cols = [col for col in stock_data.columns if col[1] != 'CUR_MKT_CAP']
            stock_data[non_mkt_cap_cols] = stock_data[non_mkt_cap_cols].ffill().bfill()

            # 移除CUR_MKT_CAP为NA的行
            mkt_cap_col = [(ticker, 'CUR_MKT_CAP')]
            stock_data = stock_data.dropna(subset=mkt_cap_col)

            all_stocks_data.append(stock_data)

        except Exception as e:
            print(f"处理 {ticker} 时出错: {str(e)}")
            continue
    # 保存数据
    if all_stocks_data:
        # 保存基础财务指标
        final_data = pd.concat(all_stocks_data, axis=1)
        filename = f"indicator_data_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
        final_data.to_csv(filename)
        print(f"指标数据已保存到 {filename}")

    # 2. 获取EVS数据
    print("\n获取EVS数据...")
    evs_data = []
    for date in trading_dates:
        date_str = date.strftime('%Y-%m-%d')
        five_years_ago = (date - pd.DateOffset(years=5)).strftime('%Y-%m-%d')
        print(f"处理 {date_str} 的EVS数据...")
        
        try:
            # SPX成分股
            formula = f'=BQL("members(\'SPX Index\')", "avg(ev_to_sales(fa_period_reference=range({five_years_ago}, {date_str}), fa_period_type=A))")'
            spx_evs = BQL(formula, ["evs_5y_avg"], 1000)
            
            # NDX成分股
            formula = f'=BQL("members(\'NDX Index\')", "avg(ev_to_sales(fa_period_reference=range({five_years_ago}, {date_str}), fa_period_type=A))")'
            ndx_evs = BQL(formula, ["evs_5y_avg"], 1000)
            
            # 合并数据并创建多级索引DataFrame
            evs_df = pd.concat([spx_evs, ndx_evs])
            evs_df = evs_df[~evs_df.index.duplicated(keep='first')]
            evs_df.sort_index(inplace=True)
            
            # 转换为与indicator相同的格式
            # 先创建所有列的数据字典
            evs_dict = {}
            for ticker in evs_df.index:
                evs_dict[(ticker, 'EVS_5Y_AVG')] = evs_df.loc[ticker, 'evs_5y_avg']
            
            # 一次性创建DataFrame
            daily_evs = pd.DataFrame(evs_dict, index=[date])
            evs_data.append(daily_evs)

        except Exception as e:
            print(f"处理 {date_str} 的EVS数据时出错: {str(e)}")
            continue
    if evs_data:
        # 保存EVS数据
        evs_final = pd.concat(evs_data)
        filename = f"evs_data_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
        evs_final.to_csv(filename)
        print(f"EVS数据已保存到 {filename}")

    # 3. 获取OPERINC数据
    print("\n获取OPERINC数据...")
    operinc_data = []
    for date in trading_dates:
        date_str = date.strftime('%Y-%m-%d')
        print(f"处理 {date_str} 的OPERINC数据...")

        try:
            # SPX成分股
            formula = f'=BQL("members(\'SPX Index\')", "oper_inc_growth(fa_act_est_data=E, fa_period_reference=2024, fa_period_type=A)", "dates={date_str}", "fill=prev")'
            spx_operinc = BQL(formula, ["operinc_growth_est12m"], 1000)

            # NDX成分股
            formula = f'=BQL("members(\'NDX Index\')", "oper_inc_growth(fa_act_est_data=E, fa_period_reference=2024, fa_period_type=A)", "dates={date_str}", "fill=prev")'
            ndx_operinc = BQL(formula, ["operinc_growth_est12m"], 1000)

            # 合并数据并创建多级索引DataFrame
            operinc_df = pd.concat([spx_operinc, ndx_operinc])
            operinc_df = operinc_df[~operinc_df.index.duplicated(keep='first')]
            operinc_df.sort_index(inplace=True)

            # 转换为与indicator相同的格式
            # 先创建所有列的数据字典
            operinc_dict = {}
            for ticker in operinc_df.index:
                operinc_dict[(ticker, 'OPERINC_GROWTH_EST12M')] = operinc_df.loc[ticker, 'operinc_growth_est12m']
            
            # 一次性创建DataFrame
            daily_operinc = pd.DataFrame(operinc_dict, index=[date])           
            operinc_data.append(daily_operinc)
            
        except Exception as e:
            print(f"处理 {date_str} 的OPERINC数据时出错: {str(e)}")
            continue
    if operinc_data:
        # 保存OPERINC数据
        operinc_final = pd.concat(operinc_data)
        filename = f"operinc_data_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
        operinc_final.to_csv(filename)
        print(f"OPERINC数据已保存到 {filename}")
        
    # 获取价格数据
    price_start_date = start_date - timedelta(days=365)
    print("\n获取价格数据...")
    price_data = blp.bdh(ticker_names.tolist(), 'PX_LAST', price_start_date, end_date)

    filename = f"price_data_{price_start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
    price_data.to_csv(filename)
    print(f"价格数据已保存到 {filename}")

if __name__ == "__main__":
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2025, 1, 11)
    collect_all_data(start_date, end_date) 