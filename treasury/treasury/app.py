import argparse
import json

import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash import dcc, html
from dash.dependencies import Input, Output, State

from treasury.callbacks import (download_full, download_full_prices, download_small, download_small_prices, get_update_balances,
                                get_update_prices, update_forecast_chart, update_price_chart, update_summary)
from treasury.data import get_gecko_spot, get_gecko_prices, lookup_balance

THEME = dbc.themes.VAPOR
TITLE = 'Symbol Treasury Analysis Tool v1.0'


def get_app(price_data_loc, account_data_loc, config, serve, base_path, start_date, end_date, auto_update_delay_seconds=600):

    app = dash.Dash(__name__, serve_locally=serve, url_base_pathname=base_path, external_stylesheets=[THEME])
    app.title = TITLE

    # preprocess data for fast load
    try:
        prices = pd.read_csv(price_data_loc, header=0, index_col=0, parse_dates=True)
    except FileNotFoundError:
        print('No price data found, pulling fresh data for assets in config (this may take a while)')
        if len(config['assets']) > 0:
            prices = []
            for asset in config['assets']:
                prices.append(get_gecko_prices(
                    asset,
                    start_date,
                    end_date,
                    config['max_api_tries'],
                    config['retry_delay_seconds']))
            prices = pd.concat(prices, axis=1).sort_index(axis=0).sort_index(axis=1)
            print(f'Prices acquired successfully; writing to {price_data_loc}')
            prices.to_csv(price_data_loc)
        else:
            print('No assets found in config; aborting!')
            raise

    lookback_prices = prices.loc[start_date:end_date]

    accounts = pd.read_csv(account_data_loc, header=0, index_col=None)
    accounts['Balance'] = [int(lookup_balance(row.Address, row.Asset, config['api_hosts'])) for row in accounts.itertuples()]
    asset_values = accounts.groupby('Asset')['Balance'].sum().to_dict()

    summary_df = pd.DataFrame.from_records({
        'Latest XYM Price': [f'${get_gecko_spot("XYM"):.4}'],
        'Latest XEM Price': [f'${get_gecko_spot("XEM"):.4}'],
        'Reference Trend (Daily)': [f'{prices[config["default_ref_ticker"]].pct_change().mean():.3%}'],
        'Reference Vol (Daily)': [f'{prices[config["default_ref_ticker"]].pct_change().std():.3%}']})

    app.layout = dbc.Container([
        dbc.Row([html.H1(TITLE)], justify='center'),
        dbc.Row([
            dbc.Table.from_dataframe(summary_df, bordered=True, color='dark')
        ], id='summary-table'),
        dbc.Row([
            dbc.Col([
                dbc.Spinner(html.Div([], id='address-table')),
                dbc.FormText(
                    'Select the asset used to seed the simulation. Historical data from this asset will be used ' +
                    'to fit a model for future price changes, which samples the possible future price paths.'),
                dbc.InputGroup(
                    [
                        dbc.InputGroupText('Reference Asset:'),
                        dbc.Select(
                            id='ref-ticker',
                            options=[{'label': ticker, 'value': ticker} for ticker in prices],
                            value=config['default_ref_ticker'])
                    ],
                    className='mb-3',
                ),
                dbc.FormText('Choose how many days into the future you wish to forecast.'),
                dbc.InputGroup(
                    [
                        dbc.InputGroupText('Forecast Days:'),
                        dbc.Input(
                            id='forecast-days',
                            value=config['default_forecast_periods'],
                            type='number',
                            min=1,
                            max=1000,
                            step=1,
                            debounce=True)
                    ],
                    className='mb-3',
                ),
                dbc.FormText(
                    'Choose how many price simulations you wish to run. More simulations will take slightly ' +
                    'longer to run, but will allow for better estimation of probabilities.'),
                dbc.InputGroup(
                    [
                        dbc.InputGroupText('Number of Simulations:'),
                        dbc.Input(id='num-sims', value=config['default_num_sims'], type='number', min=1, step=1, debounce=True)
                    ],
                    className='mb-3',
                ),
                dbc.FormText(
                    'Choose the date from which historical data will be collected. A longer data collection ' +
                    'period will result in better estimation. Can also be used to perform hypothetical analysis of past scenarios.'),
                dbc.InputGroup(
                    [
                        dbc.InputGroupText('Data Start:'),
                        dbc.Input(id='start-date', value=start_date, type='text', debounce=True)
                    ],
                    className='mb-3',
                ),
                dbc.FormText(
                    'Choose the end date for the historical data. The simulation will start from this date. ' +
                    'Values in the future or too far in the past may result in errors.'),
                dbc.InputGroup(
                    [
                        dbc.InputGroupText('Data End:'),
                        dbc.Input(id='end-date', value=end_date, type='text', debounce=True)
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
                dbc.Row([
                    dbc.Button('Download Sim Balances', id='download-button-full', color='primary', className='me-1'),
                    dbc.Button('Download High/Low/Mid Balances', id='download-button-small', color='secondary', className='me-1'),
                    dbc.Button('Download Simulated Ref Asset Prices', id='price-button-full', color='success', className='me-1'),
                    dbc.Button('Download High/Low/Mid Ref Asset Prices', id='price-button-small', color='warning', className='me-1'),
                ]),
                dcc.Download(id='download-small-dataframe'),
                dcc.Download(id='download-full-dataframe'),
                dcc.Download(id='download-small-prices'),
                dcc.Download(id='download-full-prices'),
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
        dcc.Store(id='full-prices'),
        dcc.Store(id='small-prices'),
        dcc.Store(id='full-sims'),
        dcc.Store(id='small-sims'),
        dcc.Interval(
            id='auto-update-trigger',
            interval=auto_update_delay_seconds*1000,
            n_intervals=0)
    ], fluid=True)

    app.callback(
        Output('download-full-prices', 'data'),
        Input('price-button-full', 'n_clicks'),
        State('full-prices', 'data'),
        prevent_initial_call=True)(download_full_prices)

    app.callback(
        Output('download-small-prices', 'data'),
        Input('price-button-small', 'n_clicks'),
        State('small-prices', 'data'),
        prevent_initial_call=True)(download_small_prices)

    app.callback(
        Output('download-full-dataframe', 'data'),
        Input('download-button-full', 'n_clicks'),
        State('full-sims', 'data'),
        prevent_initial_call=True)(download_full)

    app.callback(
        Output('download-small-dataframe', 'data'),
        Input('download-button-small', 'n_clicks'),
        State('small-sims', 'data'),
        prevent_initial_call=True)(download_small)

    app.callback(
        Output('summary-table', 'children'),
        Input('lookback-prices', 'data'),
        Input('ref-ticker', 'value'))(update_summary)

    app.callback(
        Output('address-table', 'children'),
        Output('asset-values', 'data'),
        Input('auto-update-trigger', 'n_intervals'))(
            get_update_balances(account_data_loc, config['api_hosts'],  config['explorer_url_map']))

    app.callback(
        Output('ref-prices', 'data'),
        Output('lookback-prices', 'data'),
        Input('start-date', 'value'),
        Input('end-date', 'value'),
        State('ref-prices', 'data'),
        State('lookback-prices', 'data'))(get_update_prices(price_data_loc, config['max_api_tries'], config['retry_delay_seconds']))

    app.callback(
        Output('forecast-graph', 'figure'),
        Output('full-sims', 'data'),
        Output('small-sims', 'data'),
        Output('full-prices', 'data'),
        Output('small-prices', 'data'),
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
    parser = argparse.ArgumentParser(description='webapp that monitors treasury balances and crypto asset prices')
    parser.add_argument('--config', '-c', help='configuration file location', default='../treasury_config.json')
    parser.add_argument('--host', help='host ip, defaults to localhost', default='127.0.0.1')
    parser.add_argument('--port', type=int, help='port for webserver', default=8080)
    parser.add_argument('--proxy', help='proxy spec of the form ip:port::gateway to render urls', default=None)
    parser.add_argument('--base-path', help='extension if server is not at root of url', default=None)
    parser.add_argument('--serve', action='store_true', help='flag to indicate whether server will recieve external requests')
    parser.add_argument('--price-data-loc', help='path to flat file storing collected data', default='../data/price_data.csv')
    parser.add_argument('--account-data-loc', help='path to csv with account information', default='../data/accounts.csv')
    parser.add_argument('--start-date', help='default start date', default='2021-12-01')
    parser.add_argument('--end-date', help='default end date', default=None)
    args = parser.parse_args()

    if args.end_date is None:
        args.end_date = (pd.to_datetime('today')-pd.Timedelta(1, unit='D')).strftime('%Y-%m-%d')

    try:
        with open(args.config) as config_file:
            args.config = json.load(config_file)
    except FileNotFoundError:
        print(f'No configuration file found at {args.config}')
        print('Configuration is required to run the app!')
        raise

    app = get_app(args.price_data_loc, args.account_data_loc, args.config, args.serve, args.base_path, args.start_date, args.end_date)
    app.run_server(host=args.host, port=args.port, threaded=True, proxy=args.proxy, debug=True)


if __name__ == '__main__':
    main()
