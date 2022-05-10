#!/bin/bash

python3 -m treasury.app --account_data_loc './data/accounts.csv' --price_data_loc './data/price_data.csv' --proxy 'http://0.0.0.0:8080::https://magicmouth.monster/treasury/' --base_path '/treasury/' --serve --host '0.0.0.0'