# import plotly.graph_objects as go
# import tensorflow_probability as tfp

# tfd = tfp.distributions

# import dash_bootstrap_components as dbc

# from data import *
# from models import *


# def update_summary(lookback_prices, ref_ticker):
#     lookback_prices = pd.read_json(lookback_prices, orient='split')
#     summary_dict={
#         'Latest XYM Price': [f"${get_gecko_spot('XYM'):.4}"],
#         'Latest XEM Price': [f"${get_gecko_spot('XEM'):.4}"],
#         'Reference Trend (Daily)': [f'{lookback_prices[ref_ticker].pct_change().mean():.3%}'],
#         'Reference Vol (Daily)': [f'{lookback_prices[ref_ticker].pct_change().std():.3%}']
#     }
#     return [dbc.Table.from_dataframe(pd.DataFrame.from_records(summary_dict), bordered=True, color='dark')]


# def update_prices(start_date, end_date, ref_prices, lookback_prices):
#     # TODO: progress bar when pulling API data?
#     if ref_prices is None:
#         ref_prices = prices.copy()
#     else:
#         ref_prices = pd.read_json(ref_prices, orient='split')
#     price_len = len(ref_prices)

#     start_date = pd.to_datetime(start_date).tz_localize('UTC')
#     end_date = pd.to_datetime(end_date).tz_localize('UTC')

#     # collect data if we don't already have what we need
#     # notify the user with an alert when we have to pull prices?
#     # could probably break this out into its own callback and add a loading bar, etc.
#     if start_date < ref_prices.index[0]:
#         new_prices = []
#         for asset in ref_prices.columns:
#             new_prices.append(get_gecko_prices(asset, start_date, ref_prices.index[0]-pd.Timedelta(days=1)))
#         new_prices = pd.concat(new_prices, axis=1)
#         ref_prices = pd.concat([new_prices, ref_prices], axis=0).sort_index().drop_duplicates()
#     if end_date > ref_prices.index[-1]:
#         new_prices = []
#         for asset in ref_prices.columns:
#             new_prices.append(get_gecko_prices(asset, ref_prices.index[-1]+pd.Timedelta(days=1), end_date))
#         new_prices = pd.concat(new_prices, axis=1)
#         ref_prices = pd.concat([ref_prices, new_prices], axis=0).sort_index().drop_duplicates()

#     if len(ref_prices) != price_len:
#         ref_prices.to_csv(PRICE_DATA_LOC)

#     lookback_prices = ref_prices.loc[start_date:end_date]

#     return ref_prices.to_json(date_format='iso', orient='split'), lookback_prices.to_json(date_format='iso', orient='split')


# def update_forecast_chart(
#     lookback_prices,
#     ref_ticker,
#     forecast_window,
#     num_sims,
#     trend_scale,
#     vol_scale,
#     risk_threshold,
#     forecast_fig):

#     lookback_prices = pd.read_json(lookback_prices, orient='split')

#     # run models
#     forecasts = get_mean_variance_forecasts(
#         lookback_prices,
#         ref_ticker,
#         forecast_window=forecast_window,
#         trend_scale=trend_scale,
#         vol_scale=vol_scale,
#         num_sims=num_sims)
    
#     # TODO: remove this global dependence on asset_values
#     # TODO: add labels to all sims that show the quantile value at that point
#     historical_value = lookback_prices.apply(lambda x: x*asset_values.get(x.name,0)).sum(axis=1)
#     forecasts = forecasts * historical_value.iloc[-1]
#     forecast_quantiles = forecasts.quantile([(1-risk_threshold)/2,(1+risk_threshold)/2],axis=1).T
#     forecast_ranks = forecasts.rank(axis=1,pct=True)
#     historical_value = pd.concat([historical_value,forecasts.quantile(0.5,axis=1).T],axis=0)
#     historical_value.drop_duplicates(inplace=True)
    
#     forecast_traces = []
#     for sim in forecasts:
#         forecast_traces.append(
#             go.Scattergl(
#                 x=forecasts.index.values, y=forecasts[sim].values,
#                 line = dict(width=1.5, color='#6f42c1'),
#                 opacity=0.1,
#                 customdata=forecast_ranks[sim],
#                 hovertemplate=(
#                     "Date: %{x}<br>" +
#                     "Treasury Value: $%{y:,.6r}<br>" +
#                     "Quantile: %{customdata:.4p}<br>" +
#                     "<extra></extra>"),
#                 showlegend=False,
#                 mode='lines'))

#     for quantile in forecast_quantiles:
#         forecast_traces.append(
#             go.Scattergl(
#                 x=forecast_quantiles.index.values, y=forecast_quantiles[quantile].values,
#                 line = dict(width=3, color='#e44d56' if quantile < 0.5 else '#33ce6e', dash='solid'),
#                 opacity=1.0,
#                 name=f'{float(quantile):.2%} risk level',
#                 showlegend=True,
#                 legendrank=1-quantile,
#                 hovertemplate=(
#                     f'<b>{float(quantile):.2%} risk level </b><br>'+
#                     "Date: %{x}<br>" +
#                     "Treasury Value: $%{y:,.6r}<br>" +
#                     "<extra></extra>"),
#                 mode='lines'))

#     forecast_traces.append(
#         go.Scattergl(
#             x = historical_value.index.values,y=historical_value.values,
#             line = dict(width=3, color='#1ea2f3'),
#             opacity=1,
#             name='Historical Value / Average',
#             hovertemplate=(
#                 "<b>Historical Value / Average</b><br>" +
#                 "Date: %{x}<br>" +
#                 "Treasury Value: $%{y:,.6r}<br>" +
#                 "<extra></extra>"),
#             showlegend=True,
#             legendrank=0,
#             mode='lines'))
    
#     if forecast_fig is None:
#         forecast_fig = go.Figure(data=forecast_traces,
#             layout=go.Layout(
#                 plot_bgcolor='#140223',
#                 paper_bgcolor='rgba(0,0,0,0)',
#                 legend=dict(bgcolor='#140223',yanchor="top",y=0.99,xanchor="left",x=0.01),
#                 showlegend=True,
#                 hovermode='closest',
#                 font=dict(size=16,color='#32fbe2'),
#                 margin=dict(b=20,l=5,r=5,t=40),
#                 xaxis=dict(linecolor='#46d4e6',gridcolor='#46d4e6',showgrid=True, showticklabels=True),
#                 yaxis=dict(linecolor='#46d4e6',gridcolor='#46d4e6',showgrid=True, zeroline=True, zerolinecolor='#46d4e6', showticklabels=True))
#                 )
#         forecast_fig.update_layout(
#             title="Historical Treasury Value With Future Simulations",
#             xaxis_title="Date",
#             yaxis_title="Value ($USD)",
#             legend_title="Quantiles",
#         )
#     else:
#         forecast_fig['data'] = forecast_traces
        
#     return forecast_fig


# def update_price_chart(lookback_prices,price_fig):

#     lookback_prices = pd.read_json(lookback_prices, orient='split')
#     lookback_returns = (lookback_prices.pct_change().fillna(0.0)+1).cumprod() - 1

#     price_traces = []
#     for asset in prices.columns:
#         price_traces.append(
#             go.Scattergl(
#                 x=lookback_returns.index.values,
#                 y=lookback_returns[asset].values,
#                 line=dict(width=2),
#                 name=asset,
#                 customdata=lookback_prices[asset],
#                 hovertemplate=(
#                     "<b>"+asset+"</b><br>" +
#                     "Date: %{x}<br>" +
#                     "Pct. Return: %{y:.2%}<br>" +
#                     "Price: $%{customdata:.4f}<br>" +
#                     "<extra></extra>"),
#                 mode='lines'))
    
#     if price_fig is None:
#         price_fig = go.Figure(data=price_traces,
#             layout=go.Layout(
#                 plot_bgcolor='#140223',
#                 paper_bgcolor='rgba(0,0,0,0)',
#                 legend=dict(bgcolor='#140223',yanchor="top",y=0.99,xanchor="left",x=0.01),
#                 showlegend=True,
#                 hovermode='closest',
#                 font=dict(size=16,color='#32fbe2'),
#                 margin=dict(b=20,l=5,r=5,t=40),
#                 xaxis=dict(linecolor='#46d4e6',gridcolor='#46d4e6',showgrid=True, showticklabels=True),
#                 yaxis=dict(linecolor='#46d4e6',gridcolor='#46d4e6',showgrid=True, zeroline=True, zerolinecolor='#46d4e6', showticklabels=True)
#                 ))
#         price_fig.update_layout(
#             title="Asset Price Change over Lookback Period",
#             xaxis_title="Date",
#             yaxis_title="% Change",
#             legend_title="Asset",
#         )
#     else:
#         price_fig['data'] = price_traces

#     return price_fig