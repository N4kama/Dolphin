from DolphinApi.DolphinApi import DolphinApi, api
from DolphinApi.config import *
from datetime import datetime
import pandas as pd
import numpy as np
import json


def to_eur(src_value):
    value, src_currency = src_value.split(' ')
    rate = api.currency_table[api.currency_table['currency']
                              == src_currency]['rate'].values[0]
    return float(value.replace(',', '.')) * float(rate)


def convert_type(df):
    for col in df.columns:
        convert_values = []
        for elt in df[col]:
            if elt is np.nan:
                convert_values.append(np.nan)
                continue
            elt_type = elt['type']
            elt_value = elt['value']
            if elt_type == 'currency_value':
                elt_value = to_eur(elt_value)
            elif elt_type == 'date':
                elt_value = datetime.strptime(elt_value, '%Y-%m-%d').date()
            elif elt_type in ['double', 'percent']:
                elt_value = float(elt_value.replace(',', '.'))
            elif elt_type in ['asset', 'int32', 'int64']:
                elt_value = int(elt_value)
            elif elt_type == 'boolean':
                elt_value = json.loads(elt_value)
            elif elt_type not in ['asset_type', 'string', 'asset_currency', 'date-time',
                                  'asset_sub_type', 'asset_status', 'asset_quote_type',
                                  'liquidity_algorithm', 'portfolio_lock_mode', 'portfolio_type']:
                print(elt)
            convert_values.append(elt_value)
        df[col] = convert_values
    return df


def clean_data_set(df):
    df.fillna(method='pad')
    return df


def get_assets(date):
    cols = ["columns=ASSET_DATABASE_ID", "columns=LABEL",
            "columns=TYPE", "columns=LAST_CLOSE_VALUE_IN_CURR",
            "columns=CURRENCY", "columns=MIN_BUY_AMOUNT"]
    endpointApi = "asset?{}&date={}".format("&".join(cols), date)
    data = pd.read_json(api.get(endpointApi))
    assets = convert_type(data)
    assets = assets[(assets['LAST_CLOSE_VALUE_IN_CURR'].notna())
                    | (assets['TYPE'] == 'PORTFOLIO')].reset_index()
    assets = assets.fillna(1)
    return assets


def get_quote(id_, start, end):
    data = api.get('asset/{}/quote?start_date={}&end_date={}'
                   .format(id_, start, end))
    return convert_type(pd.read_json(data))


def get_asset_full_info(id_):
    data = api.get('asset/')
    asset = convert_type(pd.read_json(data))
    asset[asset['ASSET_DATABASE_ID'] == id_].to_csv("test.csv")
    return asset[asset['ASSET_DATABASE_ID'] == id_]


def post_operations(ratios, ids, start, end, bench=None, frequency=None):
    """
    Post request to the API

    Parameters
    ----------
    ratios  : array
        array of the operations to compute
    ids     : array
        array the assets IDs
    start   : date
        format: 'Y-m-d'
    end     : date
        format: 'Y-m-d'
    Returns
    -------
        Dataframe of the response
    """

    payload = {'ratio': ratios,
               'asset': ids,
               'startDate': [datetime.strptime(start, "%Y-%m-%d").isoformat()],
               'endDate': [datetime.strptime(end, "%Y-%m-%d").isoformat()],
               'benchmark': bench,
               'frequency': frequency}
    data = api.post('ratio/invoke', payload)
    data = pd.read_json(data)
    operation = convert_type(data)
    operation = operation.transpose()
    operation.columns = np.array(
        [api.operations_table[api.operations_table.id == i].name.values[0] for i in ratios])
    return operation


def get_portfolio(id_):
    data = api.get('portfolio/{}/dyn_amount_compo'.format(id_))
    portfolio = pd.read_json(data)
    return portfolio


def get_portfolio_IDs():
    cols = ["columns=TYPE", "columns=ASSET_DATABASE_ID", "columns=LABEL"]
    endpointApi = "asset?{}&date={}".format("&".join(cols), start_period)
    data = pd.read_json(api.get(endpointApi))
    assets = convert_type(data)
    assets = assets[(assets['TYPE'] == 'PORTFOLIO')].reset_index()
    return assets
    portfolio_id = assets.loc[
        (assets['TYPE'] == 'PORTFOLIO') &
        (assets['LABEL'] == api.portofolio_label)]['ASSET_DATABASE_ID'].values[0]
    return int(portfolio_id)


def get_epita_portfolio_id():
    df_IDs = get_portfolio_IDs()
    return int(df_IDs.loc[df_IDs['LABEL'] == 'EPITA_PTF_4']['ASSET_DATABASE_ID'])


def get_epita_portfolio():
    epita_portfolio_id = get_epita_portfolio_id()
    return get_portfolio(epita_portfolio_id)


def get_assets_portfolio(portfolio, date):
    if date not in portfolio['values']:
        return np.NaN
    return portfolio['values'][date]


def put_portfolio(portfolio_id, df_portfolio, assets):
    label = df_portfolio['label'][0]
    currency = df_portfolio['currency'][0]
    type_ = df_portfolio['type'][0]
    date = '2016-06-01'
    form = '{{"asset":{{"asset": {}, "quantity": {}}}}},'
    assets = ''.join([form.format(int(assets.iloc[i, 0]),
                                  int(assets.iloc[i, 1]))
                      for i in range(len(assets))])[:-1]
    form = '{{"label": "{}", "currency": {{"code": "{}"}}, "type": "{}", "values": {{"{}": [{}]}}}}'
    res = form.format(label, currency, type_, date, assets)
    form = 'portfolio/{}/dyn_amount_compo'
    api.put(form.format(portfolio_id), json.loads(res))
