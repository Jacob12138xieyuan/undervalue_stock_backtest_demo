"""
股票筛选和回测结果展示界面

功能：
1. 显示基金运行期间和初始资金
2. 查看指定时间段内的低估股票及其前瞻收益
3. 展示回测结果和交易记录
"""

import streamlit as st
import pandas as pd
from datetime import datetime

# 设置页面配置
st.set_page_config(page_title="股票筛选与回测系统", layout="wide")

def load_data():
    """加载所需的数据文件"""
    try:
        screening_results = pd.read_csv('daily_screening_results.csv')
        screening_results['date'] = pd.to_datetime(screening_results['date'])
        
        daily_stats = pd.read_csv('backtest_daily_stats.csv')
        daily_stats['date'] = pd.to_datetime(daily_stats['date'])
        daily_stats.set_index('date', inplace=True)
        
        trades = pd.read_csv('backtest_trades.csv')
        trades['date'] = pd.to_datetime(trades['date'])
        
        return screening_results, daily_stats, trades
    except Exception as e:
        st.error(f"加载数据文件时出错: {str(e)}")
        return None, None, None

def main():
    st.title("股票筛选与回测系统")
    
    # 显示基金基本信息
    st.markdown("### 基金基本信息")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("基金启动日期: 2024-01-02")
    with col2:
        st.info("基金关闭日期: 2025-01-11")
    with col3:
        st.info("初始资金: $10,000,000")
    
    # 加载数据
    screening_results, daily_stats, trades = load_data()
    if screening_results is None:
        return
    
    # 日期范围选择
    st.markdown("### 选择查看时间段")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "开始日期",
            min_value=datetime(2024, 1, 2),
            max_value=datetime(2025, 1, 11),
            value=datetime(2024, 1, 2)
        )
    with col2:
        end_date = st.date_input(
            "结束日期",
            min_value=datetime(2024, 1, 2),
            max_value=datetime(2025, 1, 11),
            value=datetime(2024, 1, 2)
        )
    
    # 转换为datetime以便比较
    start_datetime = pd.to_datetime(start_date)
    end_datetime = pd.to_datetime(end_date)
    
    if start_datetime > end_datetime:
        st.error("开始日期不能晚于结束日期")
        return
    
    # 显示期间低估股票
    st.markdown("### 期间低估股票")
    period_stocks = screening_results[
        (screening_results['date'] >= start_datetime) & 
        (screening_results['date'] <= end_datetime)
    ]
    
    if not period_stocks.empty:
        # 选择要显示的列
        display_cols = ['date', 'ticker', 'type', 'price', 'return_1d', 'return_1w', 
                       'return_1m', 'return_3m', 'return_1y']
        # 重命名列以便显示
        col_names = {
            'date': '日期',
            'ticker': '股票代码',
            'type': '类型',
            'price': '价格',
            'return_1d': '1日回报',
            'return_1w': '1周回报',
            'return_1m': '1月回报',
            'return_3m': '3月回报',
            'return_1y': '1年回报'
        }
        display_df = period_stocks[display_cols].rename(columns=col_names)
        # 格式化日期和回报率
        display_df['日期'] = display_df['日期'].dt.strftime('%Y-%m-%d')
        for col in ['1日回报', '1周回报', '1月回报', '3月回报', '1年回报']:
            display_df[col] = display_df[col].apply(lambda x: f"{x:.2%}" if pd.notnull(x) else "N/A")
        st.dataframe(display_df)
    else:
        st.info("该时间段没有低估股票")
    
    # 显示期间回测统计
    st.markdown("### 期间回测统计")
    period_stats = daily_stats[
        (daily_stats.index >= start_datetime) & 
        (daily_stats.index <= end_datetime)
    ]
    
    if not period_stats.empty:
        # 显示期间汇总统计
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("期末总资产", f"${period_stats['total_assets'].iloc[-1]:,.2f}")
            st.metric("期间最高总资产", f"${period_stats['total_assets'].max():,.2f}")
        with col2:
            st.metric("期末现金", f"${period_stats['cash'].iloc[-1]:,.2f}")
            st.metric("期间累计盈亏", f"${period_stats['daily_pnl'].sum():,.2f}")
        with col3:
            st.metric("期末持仓数", period_stats['positions_count'].iloc[-1])
            st.metric("期间最大持仓数", period_stats['positions_count'].max())
        with col4:
            st.metric("期末胜率", f"{period_stats['hit_ratio'].iloc[-1]:.2%}")
            st.metric("期末累计收益率", f"{period_stats['cumulative_return'].iloc[-1]:.2%}")
        
        # 显示每日统计数据
        st.markdown("#### 每日统计数据")
        period_stats_display = period_stats.copy()
        period_stats_display.index = period_stats_display.index.strftime('%Y-%m-%d')
        st.dataframe(period_stats_display)
    else:
        st.info("该时间段没有回测数据")
    
    # 显示期间交易记录
    st.markdown("### 期间交易记录")
    period_trades = trades[
        (trades['date'] >= start_datetime) & 
        (trades['date'] <= end_datetime)
    ]
    
    if not period_trades.empty:
        # 选择要显示的列并重命名
        trade_cols = {
            'date': '日期',
            'ticker': '股票代码',
            'action': '交易类型',
            'shares': '数量',
            'price': '价格',
            'value': '交易金额'
        }
        if 'pnl' in period_trades.columns:
            trade_cols['pnl'] = '盈亏'
        
        display_trades = period_trades[trade_cols.keys()].rename(columns=trade_cols)
        # 格式化数值列
        display_trades['日期'] = display_trades['日期'].dt.strftime('%Y-%m-%d')
        display_trades['交易金额'] = display_trades['交易金额'].apply(lambda x: f"${x:,.2f}")
        if '盈亏' in display_trades.columns:
            display_trades['盈亏'] = display_trades['盈亏'].apply(lambda x: f"${x:,.2f}")
        
        st.dataframe(display_trades)
    else:
        st.info("该时间段没有交易记录")

if __name__ == "__main__":
    main() 