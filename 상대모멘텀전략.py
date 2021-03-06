import os
import glob
import pandas as pd
import numpy as np
import datetime

# 종목 데이터 읽기
files = glob.glob('*.csv')

# Monthly 데이터 저장
month_last_df = pd.DataFrame(columns=['Date','CODE','1M_RET'])
#종목 데이터프레임 생성
stock_df = pd.DataFrame(columns=['Date','CODE','Adj Close'])

def data_preprocessing(samlpe, ticker, base_date):
    samlpe['CODE'] = ticker # 종목 코드 추가
    samlpe = samlpe[samlpe['Date'] >= base_date][['Date','CODE','Adj Close']].copy()
    # 기준일자 이후 데이터 사용
    samlpe.reset_index(inplace= True, drop= True)
    samlpe['STD_YM'] = samlpe['Date'].map(lambda x : datetime.datetime.strptime(x, '%Y-%m-%d').strftime('%Y-%m')) # 기준년월
    samlpe['1M_RET'] = 0.0 # 수익률 컬럼
    ym_keys = list(samlpe['STD_YM'].unique()) # 중복 제거한 기준년월 목록
    return samlpe, ym_keys

def create_trade_book(sample, sample_codes):
    book = pd.DataFrame()
    book = sample[sample_codes].copy()
    book['STD_YM'] = book.index.map(lambda x : datetime.datetime.strptime(x, '%Y-%m-%d').strftime('%Y-%m'))
    for c in sample_codes:
        book['p '+c] = ''
        book['r '+c] = ''
    return book

def tradings(book, s_codes):
    std_ym = ''
    buy_phase = False
    for s in s_codes:
        print(s)
        for i in book.index:
            if book.loc[i, 'p '+s] == '' and book.shift(1).loc[i,'p '+s] == 'ready ' + s:
                std_ym = book.loc[i, 'STD_YM']
                buy_phase = True
            if book.loc[i, 'p '+s] == '' and book.shift(1).loc[i,'STD_YM'] == std_ym and buy_phase == True:
                book.loc[i,'p '+s] = 'buy ' +s
            if book.loc[i,'p '+s] == '':
                std_ym = None
                buy_phase = False
        return book
    
def multi_returns(book, s_codes):
    # 손익계산
    rtn = 0.0
    buy_dict = {}
    num = len(s_codes)
    sell_dict = {}
    
    for i in book.index:
        for s in s_codes:
            if book.lic[i, 'p ' + s] == 'buy ' + s and book.shift(1).loc[i, 'p '+s] == 'ready '+s and book.shift(2).loc[i, 'p '+s] == '' :
                # long 진입
                buy_dict[s] = book.loc[i, s]
            elif book.lic[i, 'p ' + s] == '' and book.shift(1).loc[i, 'p '+s] == 'buy '+s: # long 청산
                sell_dict[s] = book.loc[i, s]
                # 손익계산
                rtn = (sell_dict[s] / buy_dict[s]) -1
                book.loc[i, 'r '+s] = rtn
                print('개별 청산일 : ', i, ' 종목 코드 : ', s, 'long 진입가격 : ', buy_dict[s], ' | long 청산가격 : ', sell_dict[s], ' | return:', round(rtn * 100, 2), '%') # 수익률 계산
            if book.loc[i, 'p ',+s] == '': # 제로 포지션 || long 청산
                buy_dict[s] = 0.0
                sell_dict[s] = 0.0
        acc_rtn = 1.0
        for i in book.index:
            rtn = 0.0
            count = 0
            for s in s_codes:
                if book.loc[i, 'p '+s] == '' and book.shift(1).loc[i, 'p '+s] == 'buy '+s:
                    count += 1
                    rtn += book.loc[i, 'r '+s]
            if (rtn != 0.0) & (count != 0) :
                acc_rtn *= (rtn / count) + 1
                print('누적 청산일 : ',i,'청산 종목수 : ', count, '청산 수익률 : ', round((rtn/count), 4),'누적 수익률 : ', round(acc_rtn, 4))
            book.loc[i, 'acc_rtn'] = acc_rtn
        print('누적 수익률 : ', round(acc_rtn, 4))

for file in files :
    '''
    데이터 저장 경로에 있는 개별 종목들을 읽어옴
    '''
    if os.path.isdir(file):
        print('%s <DIR> '%file)
    else:
        folder, name = os.path.split(file)
        head, tail = os.path.splitext(name)
        print(file)
        read_df = pd.read_csv(file)
        # 데이터 가공
        price_df, ym_keys = data_preprocessing(read_df,head,base_date='2019-12-12')
        # 가공한 데이터 붙이기
        stock_df = stock_df.append(price_df.loc[:,['Date','CODE','Adj Close']],sort=False)
        # 월별 상대 모멘텀 계산을 위한 1개월간 수익률 계산
        for ym in ym_keys:
            m_ret = price_df.loc[price_df[price_df['STD_YM'] == ym].index[-1], 'Adj Close'] / price_df.loc[price_df[price_df['STD_YM'] == ym].index[0], 'Adj Close']
            price_df.loc[price_df['STD_YM'] == ym, ['1M_RET']] = m_ret
            month_last_df = month_last_df.append(price_df.loc[price_df[price_df['STD_YM'] == ym].index[-1], ['Date','CODE','1M_RET']])

# 상대 모멘텀 수익률로 필터링
month_ret_df = month_last_df.pivot('Date', 'CODE', '1M_RET').copy()
month_ret_df = month_ret_df.rank(axis=1, ascending=False, method="max", pct=True)
# 투자종목 선택할 rank, 상위 40% 종목만 신호 목록
month_ret_df = month_ret_df.where( month_ret_df < 0.4, np.nan)
month_ret_df.fillna(0,inplace=True)
month_ret_df[month_ret_df != 0] = 1
stock_codes = list(stock_df['CODE'].unique())

print(month_ret_df)

# 신호 목록으로 트레이딩 + 포지셔닝
sig_dict = dict()
for date in month_ret_df.index:
    ticker_list = list(month_ret_df.loc[date,month_ret_df.loc[date,:] >= 1.0].index)
    sig_dict[date] = ticker_list
stock_c_matrix = stock_df.pivot('Date','CODE','Adj Close').copy()
book = create_trade_book(stock_c_matrix, list(stock_df['CODE'].unique()))

for date,values in sig_dict.items():
    for stock in values:
        book.loc[date,'p '+stock] = 'ready ' + stock

# 트레이딩
book = tradings(book, stock_codes)

# 수익률 계산
multi_returns(book, stock_codes)