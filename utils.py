import pandas as pd
import time
from datetime import datetime, timedelta
from xbbg import blp
import win32com.client as wc
import backtrader as bt

def get_index_members():
    """获取SPX和NDX成分股"""
    # 定义要获取的指数
    Index = ["SPX Index","NDX Index"]
    # 使用Bloomberg API获取成分股列表
    Index_Members_List = blp.bds(tickers=Index, flds=["INDX_MEMBERS"])
    # 去除重复项（部分股票可能同时在SPX和NDX中）
    Index_Members_List = Index_Members_List.drop_duplicates()
    # 重置索引
    Index_Members_List.index = list(range(len(Index_Members_List)))
    Index_Members_List.columns = ["ticker"]
    return Index_Members_List


def BQL(formula, colnames, timeout=500):
    # Get a dispatch interface for the Excel app
    _xl = wc.Dispatch("Excel.Application")
    
    # Ensure the Bloomberg addin is loaded
    _xl.Workbooks.Open('C:/blp/API/Office Tools/BloombergUI.xla')

    # Create a new workbook
    wb = _xl.Workbooks.Add()
    ws = wb.Sheets(1)
    cl = ws.Cells(1, 1)  # Cell A1 on Sheet 1

    # Define BQL query, and set cell formula
    qry = formula
    cl.Formula = qry
    _xl.Calculate()

    # Check the cell's value: it will likely be #N/A ...
    res = cl.Value
    nLoop = 0
    nTimeout = timeout  # ie 30 seconds

    # Loop until either get a non-# return or timeout
    while res[0] == '#' and nLoop <= nTimeout:
        time.sleep(0.1)  # 100 ms
        res = cl.Value
        nLoop += 1

    if res[0] == '#':
        print('Timed out')

    f = cl.Formula
    rc = f.split(',')[-1].split(';')
    cols = int(rc[0].split('=')[1])
    s = rc[1].split('=')[1]
    rows = int(s[0:len(s) - 2])

    # Retrieve the values from this new range
    data = ws.Range(cl, ws.Cells(rows, cols)).Value

    # Convert to DataFrame
    df = pd.DataFrame(data[1:], columns=data[0])
    # print(df)
    df.index = df["ID"]
    df.index.name = "Index"
    df = df.drop(labels="ID", axis=1)
    df.columns = colnames
    df["ticker"] = df.index

    # Tidy up
    wb.Close(SaveChanges=False)  # 添加SaveChanges=False
    _xl.Application.Quit()  # 使用Application.Quit()
    del _xl  # 添加这一行释放COM对象

    return df
