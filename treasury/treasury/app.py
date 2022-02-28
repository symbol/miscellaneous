import argparse

import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash import dcc, html
from dash.dependencies import Input, Output, State
from data import get_gecko_spot, lookup_balance

from callbacks import update_summary, update_prices, update_price_chart, update_forecast_chart

# defaults for startup
START_DATE = '2021-12-01'
END_DATE = pd.to_datetime('today').strftime('%Y-%m-%d')
FORECAST_PERIODS = 90
NUM_SIMS = 1000
REF_TICKER = 'XEM'
THEME = dbc.themes.VAPOR
TITLE = 'Symbol Treasury Analysis Tool v1.0'

COLOR_DICT = {
    'XEM': '#67b9e8',
    'XYM': '#44004e',
    'BTC': '#f7931a',
    'ETH': '#373737'
}

# TODO: figure out how to automate chart colors from stylesheet


def get_app(prices, lookback_prices, summary_df, accounts, asset_values, serve, base_path):

    app = dash.Dash(__name__, serve_locally=serve, url_base_pathname=base_path, external_stylesheets=[THEME])
    app.title = TITLE

    accounts = accounts.copy()
    accounts['Address'] = accounts['Address'].apply(lambda x: html.A(f'{x[:10]}...', href=f'https://symbol.fyi/accounts/{x}'))

    app.layout = dbc.Container([
        dbc.Row([html.H1(TITLE)], justify='center'),
        dbc.Row([
            dbc.Table.from_dataframe(summary_df, bordered=True, color='dark')
        ], id='summary-table'),
        dbc.Row([
            dbc.Col([
                dbc.Table.from_dataframe(accounts[['Name', 'Balance', 'Address']], bordered=True, color='dark', id='address-table'),
                dbc.FormText(
                    'Select the asset used to seed the simulation. Historical data from this asset will be used ' +
                    'to fit a model for future price changes, which samples the possible future price paths.'),
                dbc.InputGroup(
                    [
                        dbc.InputGroupText('Reference Asset:'),
                        dbc.Select(id='ref-ticker', options=[{'label': ticker, 'value': ticker} for ticker in prices], value='XYM')
                    ],
                    className='mb-3',
                ),
                dbc.FormText('Choose how many days into the future you wish to forecast.'),
                dbc.InputGroup(
                    [
                        dbc.InputGroupText('Forecast Days:'),
                        dbc.Input(id='forecast-days', value=FORECAST_PERIODS, type='number', min=1, max=1000, step=1, debounce=True)
                    ],
                    className='mb-3',
                ),
                dbc.FormText(
                    'Choose how many price simulations you wish to run. More simulations will take slightly ' +
                    'longer to run, but will allow for better estimation of probabilities.'),
                dbc.InputGroup(
                    [
                        dbc.InputGroupText('Number of Simulations:'),
                        dbc.Input(id='num-sims', value=NUM_SIMS, type='number', min=1, step=1, debounce=True)
                    ],
                    className='mb-3',
                ),
                dbc.FormText(
                    'Choose the date from which historical data will be collected. A longer data collection ' +
                    'period will result in better estimation. Can also be used to perform hypothetical analysis of past scenarios.'),
                dbc.InputGroup(
                    [
                        dbc.InputGroupText('Data Start:'),
                        dbc.Input(id='start-date', value=START_DATE, type='text', debounce=True)
                    ],
                    className='mb-3',
                ),
                dbc.FormText(
                    'Choose the end date for the historical data. The simulation will start from this date. ' +
                    'Values in the future or too far in the past may result in errors.'),
                dbc.InputGroup(
                    [
                        dbc.InputGroupText('Data End:'),
                        dbc.Input(id='end-date', value=END_DATE, type='text', debounce=True)
                    ],
                    className='mb-3',
                ),
                dbc.FormText(
                    'Pick a threshold percentage used to calculate the best and worst case estimates. A value ' +
                    'of 95% means that the high and low bars shown will contain an (estimated) 95% of possible scenarios. ' +
                    'Set to 100% to see the absolute minimum and maximum from the simulation.'),
                dbc.InputGroup(
                    [
                        dbc.InputGroupText('Risk Threshold:'),
                        dbc.Input(id='risk-threshold', value=0.95, type='number', min=0.0, max=1.0, debounce=True)
                    ],
                    className='mb-3',
                ),
                dbc.FormText(
                    'Set a value that scales the trend seen in the historical data. For example, a value of 3 ' +
                    'will cause the simulation to trend 3 times as strongly as the historical data, and a value of -1 will ' +
                    'reverse the trend in the historical data.'),
                dbc.InputGroup(
                    [
                        dbc.InputGroupText('Trend Multiplier:'),
                        dbc.Input(id='trend-scale', value=1.0, type='number', debounce=True)
                    ],
                    className='mb-3',
                ),
                dbc.FormText(
                    'Set a value that scales the volatility seen in the historical data. For example, value of ' +
                    '2 will cause the simulation to be twice as volatile as the historical data. Must be greater than zero.'),
                dbc.InputGroup(
                    [
                        dbc.InputGroupText('Volatility Multiplier:'),
                        dbc.Input(id='vol-scale', value=1.0, type='number', min=0.1, debounce=True)
                    ],
                    className='mb-3',
                ),
                ],
                className='col-lg-4 col-md-12',
            ),
            dbc.Col([
                dbc.Spinner(
                    dcc.Graph(
                        id='forecast-graph',
                        style={'width': '100%', 'height': '60vh'},
                        config={'scrollZoom': False},
                        responsive=True)),
                dbc.Spinner(
                    dcc.Graph(
                        id='price-graph',
                        style={'width': '100%', 'height': '60vh'},
                        config={'scrollZoom': False},
                        responsive=True)),
                ],
                className='p-3 col-lg-8 col-md-12 col-sm-12',
                width=8,
            ),
        ], className='p-3'),
        dcc.Store(id='ref-prices', data=prices.to_json(date_format='iso', orient='split')),
        dcc.Store(id='lookback-prices', data=lookback_prices.to_json(date_format='iso', orient='split')),
        dcc.Store(id='asset-values', data=asset_values),
    ], fluid=True)

    # TODO: spot updates should trigger every minute

    app.callback(
        Output('summary-table', 'children'),
        Input('lookback-prices', 'data'),
        Input('ref-ticker', 'value'))(update_summary)

    app.callback(
        Output('ref-prices', 'data'),
        Output('lookback-prices', 'data'),
        Input('start-date', 'value'),
        Input('end-date', 'value'),
        State('ref-prices', 'data'),
        State('lookback-prices', 'data'))(update_prices)

    app.callback(
        Output('forecast-graph', 'figure'),
        Input('lookback-prices', 'data'),
        Input('ref-ticker', 'value'),
        Input('forecast-days', 'value'),
        Input('num-sims', 'value'),
        Input('trend-scale', 'value'),
        Input('vol-scale', 'value'),
        Input('risk-threshold', 'value'),
        State('forecast-graph', 'figure'),
        State('asset-values', 'data'))(update_forecast_chart)

    app.callback(
        Output('price-graph', 'figure'),
        Input('lookback-prices', 'data'),
        State('price-graph', 'figure'))(update_price_chart)

    return app


def main():
    parser = argparse.ArgumentParser(description='webapp that processes data files and renders fork information')
    # parser.add_argument('--resources', help='directory containing resources', required=True)
    parser.add_argument('--host', help='host ip, defaults to localhost', default='127.0.0.1')
    parser.add_argument('--port', type=int, help='port for webserver', default=8080)
    parser.add_argument('--proxy', help='proxy spec of the form ip:port::gateway to render urls', default=None)
    parser.add_argument('--base_path', help='extension if server is not at root of url', default=None)
    parser.add_argument('--serve', action='store_true', help='flag to indicate whether server will recieve external requests')
    parser.add_argument('--price_data_loc', help='path to flat file storing collected data', default='../data/price_data.csv')
    parser.add_argument('--accounts_loc', help='path to csv with account information', default='../data/accounts.csv')
    parser.add_argument('--start_date', help='default start date', default='2021-12-01')
    parser.add_argument('--end_date', help='default end date', default=None)
    args = parser.parse_args()

    if args.end_date is None:
        args.end_date = pd.to_datetime('today').strftime('%Y-%m-%d')

    # prep data
    prices = pd.read_csv(args.price_data_loc, header=0, index_col=0, parse_dates=True)
    lookback_prices = prices.loc[START_DATE:END_DATE]

    # TODO: account values should be in app state, prices should be stored locally
    accounts = pd.read_csv(args.accounts_loc, header=0, index_col=None)
    accounts['Balance'] = [int(lookup_balance(row.Address, row.Asset)) for row in accounts.itertuples()]
    asset_values = accounts.groupby('Asset')['Balance'].sum().to_dict()

    summary_df = pd.DataFrame.from_records({
        'Latest XYM Price': [f'${get_gecko_spot("XYM"):.4}'],
        'Latest XEM Price': [f'${get_gecko_spot("XEM"):.4}'],
        'Reference Trend (Daily)': [f'{prices[REF_TICKER].pct_change().mean():.3%}'],
        'Reference Vol (Daily)': [f'{prices[REF_TICKER].pct_change().std():.3%}']})

    app = get_app(prices, lookback_prices, summary_df, accounts, asset_values, args.serve, args.base_path)
    app.run_server(host=args.host, port=args.port, threaded=True, proxy=args.proxy, debug=True)


if __name__ == '__main__':
    main()
