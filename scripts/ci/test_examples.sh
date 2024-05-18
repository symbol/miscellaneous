#!/bin/bash

set -ex

# purge output directory
rm -rf _generated && mkdir _generated

# run account scripts
python -m account.symbol_multisig_create --input account/samples/symbol_multisig_create.yaml
python -m account.symbol_multisig_relink --input account/samples/symbol_multisig_relink.yaml
python -m account.two_part_send --input account/samples/two_part_send.yaml
python -m account.verify_ownership --input account/samples/verify_ownership.yaml --allow-export

# run health scripts
python -m health.check_nem_balances --resources templates/nem.mainnet.yaml --groups core
python -m health.check_nem_balances --resources templates/symbol.mainnet.yaml --groups core

# run network scripts
python -m network.richlist_symbol --resources templates/symbol.mainnet.yaml --min-balance 50000000 --output _generated/50M.csv
python -m network.harvester --resources templates/nem.mainnet.yaml --days 0.01 --output _generated/nem_harvesters.csv
python -m network.harvester --resources templates/symbol.mainnet.yaml --days 0.01 --output _generated/symbol_harvesters.csv

# run network scripts (crawl)
python -m network.nodes --resources templates/nem.mainnet.yaml --timeout 1 --output _generated/nemnodes.json

# TODO: these are long running

# # run history scripts (nem)
# python -m history.downloader --input templates/nem.mainnet.yaml --start-date 2021-08-01 --end-date 2021-08-31 --output _generated/raw
# mkdir -p _generated/all
# python -m history.merger --input _generated/raw --output _generated/all/full.csv --ticker nem
# mkdir -p _generated/account
# python -m history.grouper --input _generated/all/full.csv --output _generated/account/grouped.csv --mode account
# python -m history.summarizer --input _generated/account --output _generated/balances.csv --mode account
# #         note: reconciler will fail when there is only a partial download
# python -m history.reconciler --input _generated/balances.csv --resources templates/nem.mainnet.yaml --mode spot || test $? -eq 1

# # run history scripts (symbol)
# python -m history.downloader --input templates/symbol.mainnet.yaml --start-date 2021-08-01 --end-date 2021-08-31 --output _generated/raw
# mkdir -p _generated/all
# python -m history.merger --input _generated/raw --output _generated/all/full.csv --ticker symbol
# mkdir -p _generated/account
# python -m history.grouper --input _generated/all/full.csv --output _generated/account/grouped.csv --mode account
# python -m history.summarizer --input _generated/account --output _generated/balances.csv --mode account
# #         note: reconciler will fail when there is only a partial download
# python -m history.reconciler --input _generated/balances.csv --resources templates/symbol.mainnet.yaml --mode spot || test $? -eq 3
