import argparse

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html
from dash.dependencies import Input, Output, State
from data import get_gecko_prices, get_gecko_spot, lookup_balance
from models import get_mean_variance_forecasts

# from callbacks import *

# defaults for startup
START_DATE = '2021-12-01'
END_DATE = pd.to_datetime('today').strftime('%Y-%m-%d')
FORECAST_PERIODS = 90
NUM_SIMS = 1000
REF_TICKER = 'XEM'
THEME = dbc.themes.VAPOR
PRICE_DATA_LOC = 'price_data.csv'
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
        dcc.Store(id='ref-prices'),
        dcc.Store(id='lookback-prices')
    ], fluid=True)

    # TODO: spot updates should trigger every minute

    @app.callback(
        Output('summary-table', 'children'),
        Input('lookback-prices', 'data'),
        Input('ref-ticker', 'value'))
    def update_summary(lookback_prices, ref_ticker):
        lookback_prices = pd.read_json(lookback_prices, orient='split')
        summary_dict = {
            'Latest XYM Price': [f"${get_gecko_spot('XYM'):.4}"],
            'Latest XEM Price': [f"${get_gecko_spot('XEM'):.4}"],
            'Reference Trend (Daily)': [f'{lookback_prices[ref_ticker].pct_change().mean():.3%}'],
            'Reference Vol (Daily)': [f'{lookback_prices[ref_ticker].pct_change().std():.3%}']
        }
        return [dbc.Table.from_dataframe(pd.DataFrame.from_records(summary_dict), bordered=True, color='dark')]

    @app.callback(
        Output('ref-prices', 'data'),
        Output('lookback-prices', 'data'),
        Input('start-date', 'value'),
        Input('end-date', 'value'),
        State('ref-prices', 'data'),
        State('lookback-prices', 'data'))
    def update_prices(
        start_date, 
        end_date,
        ref_prices, 
        lookback_prices):

        # TODO: progress bar when pulling API data?
        if ref_prices is None:
            ref_prices = prices.copy()
        else:
            ref_prices = pd.read_json(ref_prices, orient='split')
        price_len = len(ref_prices)

        start_date = pd.to_datetime(start_date).tz_localize('UTC')
        end_date = pd.to_datetime(end_date).tz_localize('UTC')

        # collect data if we don't already have what we need
        # notify the user with an alert when we have to pull prices?
        # could probably break this out into its own callback and add a loading bar, etc.
        if start_date < ref_prices.index[0]:
            new_prices = []
            for asset in ref_prices.columns:
                new_prices.append(get_gecko_prices(asset, start_date, ref_prices.index[0]-pd.Timedelta(days=1)))
            new_prices = pd.concat(new_prices, axis=1)
            ref_prices = pd.concat([new_prices, ref_prices], axis=0).sort_index().drop_duplicates()
        if end_date > ref_prices.index[-1]:
            new_prices = []
            for asset in ref_prices.columns:
                new_prices.append(get_gecko_prices(asset, ref_prices.index[-1]+pd.Timedelta(days=1), end_date))
            new_prices = pd.concat(new_prices, axis=1)
            ref_prices = pd.concat([ref_prices, new_prices], axis=0).sort_index().drop_duplicates()

        if len(ref_prices) != price_len:
            ref_prices.to_csv(PRICE_DATA_LOC)

        lookback_prices = ref_prices.loc[start_date:end_date]

        return ref_prices.to_json(date_format='iso', orient='split'), lookback_prices.to_json(date_format='iso', orient='split')

    @app.callback(
        Output('forecast-graph', 'figure'),
        Input('lookback-prices', 'data'),
        Input('ref-ticker', 'value'),
        Input('forecast-days', 'value'),
        Input('num-sims', 'value'),
        Input('trend-scale', 'value'),
        Input('vol-scale', 'value'),
        Input('risk-threshold', 'value'),
        State('forecast-graph', 'figure'))
    def update_forecast_chart(
        lookback_prices,
        ref_ticker,
        forecast_window,
        num_sims,
        trend_scale,
        vol_scale,
        risk_threshold,
        forecast_fig):

        lookback_prices = pd.read_json(lookback_prices, orient='split')

        # run models
        forecasts = get_mean_variance_forecasts(
            lookback_prices,
            ref_ticker,
            forecast_window=forecast_window,
            trend_scale=trend_scale,
            vol_scale=vol_scale,
            num_sims=num_sims)

        # TODO: remove this global dependence on asset_values
        # TODO: add labels to all sims that show the quantile value at that point
        historical_value = lookback_prices.apply(lambda x: x*asset_values.get(x.name, 0)).sum(axis=1)
        forecasts = forecasts * historical_value.iloc[-1]
        forecast_quantiles = forecasts.quantile([(1-risk_threshold)/2, (1+risk_threshold)/2], axis=1).T
        forecast_ranks = forecasts.rank(axis=1, pct=True)
        historical_value = pd.concat([historical_value, forecasts.quantile(0.5, axis=1).T], axis=0)
        historical_value.drop_duplicates(inplace=True)

        forecast_traces = []
        for sim in forecasts:
            forecast_traces.append(
                go.Scattergl(
                    x=forecasts.index.values,
                    y=forecasts[sim].values,
                    line=dict(width=1.5, color='#6f42c1'),
                    opacity=0.1,
                    customdata=forecast_ranks[sim],
                    hovertemplate=(
                        "Date: %{x}<br>" +
                        "Treasury Value: $%{y:,.6r}<br>" +
                        "Quantile: %{customdata:.4p}<br>" +
                        "<extra></extra>"),
                    showlegend=False,
                    mode='lines'))

        for quantile in forecast_quantiles:
            forecast_traces.append(
                go.Scattergl(
                    x=forecast_quantiles.index.values,
                    y=forecast_quantiles[quantile].values,
                    line=dict(
                        width=3,
                        color='#e44d56' if quantile < 0.5 else '#33ce6e',
                        dash='solid'),
                    opacity=1.0,
                    name=f'{float(quantile):.2%} risk level',
                    showlegend=True,
                    legendrank=1 - quantile,
                    hovertemplate=(
                        f'<b>{float(quantile):.2%} risk level </b><br>' +
                        "Date: %{x}<br>" +
                        "Treasury Value: $%{y:,.6r}<br>" +
                        "<extra></extra>"),
                    mode='lines'))

        forecast_traces.append(
            go.Scattergl(
                x=historical_value.index.values,
                y=historical_value.values,
                line=dict(width=3, color='#1ea2f3'),
                opacity=1,
                name='Historical Value / Average',
                hovertemplate=(
                    "<b>Historical Value / Average</b><br>" +
                    "Date: %{x}<br>" +
                    "Treasury Value: $%{y:,.6r}<br>" +
                    "<extra></extra>"),
                showlegend=True,
                legendrank=0,
                mode='lines'))

        if forecast_fig is None:
            forecast_fig = go.Figure(
                data=forecast_traces,
                layout=go.Layout(
                    plot_bgcolor='#140223',
                    paper_bgcolor='rgba(0,0,0,0)',
                    legend=dict(
                        bgcolor='#140223',
                        yanchor="top",
                        y=0.99,
                        xanchor="left",
                        x=0.01),
                    showlegend=True,
                    hovermode='closest',
                    font=dict(size=16, color='#32fbe2'),
                    margin=dict(b=20, l=5, r=5, t=40),
                    xaxis=dict(
                        linecolor='#46d4e6',
                        gridcolor='#46d4e6',
                        showgrid=True,
                        showticklabels=True),
                    yaxis=dict(
                        linecolor='#46d4e6',
                        gridcolor='#46d4e6',
                        showgrid=True,
                        zeroline=True,
                        zerolinecolor='#46d4e6',
                        showticklabels=True)))
            forecast_fig.update_layout(
                title="Historical Treasury Value With Future Simulations",
                xaxis_title="Date",
                yaxis_title="Value ($USD)",
                legend_title="Quantiles")
        else:
            forecast_fig['data'] = forecast_traces
            
        return forecast_fig

    @app.callback(
        Output('price-graph', 'figure'),
        Input('lookback-prices', 'data'),
        State('price-graph', 'figure'))
    def update_price_chart(lookback_prices, price_fig):

        lookback_prices = pd.read_json(lookback_prices, orient='split')
        lookback_returns = (lookback_prices.pct_change().fillna(0.0)+1).cumprod() - 1

        price_traces = []
        for asset in prices.columns:
            price_traces.append(
                go.Scattergl(
                    x=lookback_returns.index.values,
                    y=lookback_returns[asset].values,
                    line=dict(width=2),  # , color=COLOR_DICT.get(asset,'#ffffff')),
                    name=asset,
                    customdata=lookback_prices[asset],
                    hovertemplate=(
                        "<b>"+asset+"</b><br>" +
                        "Date: %{x}<br>" +
                        "Pct. Return: %{y:.2%}<br>" +
                        "Price: $%{customdata:.4f}<br>" +
                        "<extra></extra>"),
                    mode='lines'))

        if price_fig is None:
            price_fig = go.Figure(
                data=price_traces,
                layout=go.Layout(
                    plot_bgcolor='#140223',
                    paper_bgcolor='rgba(0,0,0,0)',
                    legend=dict(
                        bgcolor='#140223',
                        yanchor="top",
                        y=0.99,
                        xanchor="left",
                        x=0.01),
                    showlegend=True,
                    hovermode='closest',
                    font=dict(size=16, color='#32fbe2'),
                    margin=dict(b=20, l=5, r=5, t=40),
                    xaxis=dict(
                        linecolor='#46d4e6',
                        gridcolor='#46d4e6',
                        showgrid=True,
                        showticklabels=True),
                    yaxis=dict(
                        linecolor='#46d4e6',
                        gridcolor='#46d4e6',
                        showgrid=True,
                        zeroline=True,
                        zerolinecolor='#46d4e6',
                        showticklabels=True)))
            price_fig.update_layout(
                title="Asset Price Change over Lookback Period",
                xaxis_title="Date",
                yaxis_title="% Change",
                legend_title="Asset")
        else:
            price_fig['data'] = price_traces

        return price_fig

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
    prices = pd.read_csv(PRICE_DATA_LOC, header=0, index_col=0, parse_dates=True)
    lookback_prices = prices.loc[START_DATE:END_DATE]

    # TODO: account values should be in app state, prices should be stored locally
    accounts = pd.read_csv(args.accounts_loc, header=0, index_col=None)
    accounts['Balance'] = [int(lookup_balance(row.Address, row.Asset)) for row in accounts.itertuples()]
    asset_values = accounts.groupby('Asset')['Balance'].sum().to_dict()

    summary_df = pd.DataFrame.from_records({
        'Latest XYM Price': [f"${get_gecko_spot('XYM'):.4}"],
        'Latest XEM Price': [f"${get_gecko_spot('XEM'):.4}"],
        'Reference Trend (Daily)': [f'{prices[REF_TICKER].pct_change().mean():.3%}'],
        'Reference Vol (Daily)': [f'{prices[REF_TICKER].pct_change().std():.3%}']})

    app = get_app(prices, lookback_prices, summary_df, accounts, asset_values, args.serve, args.base_path)
    app.run_server(host=args.host, port=args.port, threaded=True, proxy=args.proxy, debug=True)


if __name__ == '__main__':
    main()
