#!/bin/bash

python3 -m treasury.app --account-data-loc './data/accounts.csv' --price-data-loc './data/price_data.csv' --serve --host '0.0.0.0'
