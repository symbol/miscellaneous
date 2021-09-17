# Miscellany

## account

### symbol_multisig_create

_prepares transactions for creating symbol multisig accounts_

Creates an aggregate transaction containing an embedded multisig account modification transaction signed by all cosigners.

Example: prepare transactions as described in `account/samples/symbol_multisig_create.yaml`.

```sh
python -m account.symbol_multisig_create --input account/samples/symbol_multisig_create.yaml
```

### two_part_send

_prepares transactions for sending tokens from one account to another in two phases_

Phase One can be used to send a small amount to the destination account to be used as a correctness check.
Phase Two can be used to send the remainder after Phase One succeeds.

Example: prepare transactions as described in `account/samples/two_part_send.yaml`.

```sh
python -m account.two_part_send --input account/samples/two_part_send.yaml
```

### verify_ownership

_verifies account derivations from a BIP32 seed and passphrase_

Compares BIP32 derivation paths to expected accounts.

Example: check accounts in `account/samples/verify_ownership.yaml`.

```sh
python -m account.verify_ownership --input account/samples/verify_ownership.yaml
```

## health

### check_nem_balances

_check balances of multiple accounts in a network_

Prints balance and last harvest information for a set of NEM and/or Symbol accounts.

Example: load accounts and nodes from `templates/symbol.mainnet.yaml` and print all accounts with role `core`.

```sh
python -m health.check_nem_balances --resources templates/symbol.mainnet.yaml --groups core
```

```sh
 UTC Time: 2021-07-30 18:15:59.437878
XYM Price: 0.115421

| [SYMBOL @ 390742] CORE ACCOUNTS          | PK  | TYPE | IMPORTA |  HARVEST HEIGHT  | Balance              | V % |
-------------------------------------------------------------------------------------------------------------------
| NBMDALVKGYK562LXSESZT6FFNI65FDXFY5VOXSQ  |  X  | UNLI | 0.00033 |       0    NEVER |     3,125,000.000003 | N/A |
| NABH3A5VDLYAVA73OV246JTVMAIPD2WEMAQL27I  |  X  | MAIN | 0.00033 |  390561 ~ 90.50M |     3,101,302.375428 | N/A |
| NAL4XHZU6MANNNFQI4Z2WNMU3KRI2YW2MRRMHLI  |  X  | MAIN | 0.00033 |  388170 ~ 21.43H |     3,106,297.223537 | N/A |
-------------------------------------------------------------------------------------------------------------------
9,332,599.598968 (~$1,077,177.91 USD)
-------------------------------------------------------------------------------------------------------------------
```

## history

### downloader

_download transactions from nem or symbol networks_

Retrieves balance change events for a set of accounts over a specified date range.

Example: download all June 2021 balance change events for the accounts in `templates/symbol.mainnet.yaml` and save the data in `_histout/raw`.

```sh
python -m history.downloader --input templates/symbol.mainnet.yaml --start-date 2021-06-01 --end-date 2021-06-30 --output _histout/raw
```

### merger

_generates a merged pricing and account report_

Merges all the of the raw downloaded data into a single unified report file.

Example: merge the downloaded data in `_histout/raw` into `_histout/all/full.csv` using prices for `symbol`.

```sh
mkdir -p _histout/all
python -m history.merger --input _histout/raw --output _histout/all/full.csv --ticker symbol
```

### grouper

_produces grouped report by aggregating input data based on mode_

Groups the data in a unified report file by one of the following `mode`s:

| report name | grouping key |
| :-- | :-- |
| account | account |
| account_tag | (account, tag) |
| daily | (day, tag) |
| tag | tag |

Example: Group data in ` _histout/all/full.csv` by `account` and produce a new `_histout/account/grouped.csv` report.

```sh
mkdir -p _histout/account
python -m history.grouper --input _histout/all/full.csv --output _histout/account/grouped.csv --mode account
```

### summarizer

_generates a balance table based on options_

Produces a balance table from multiple grouped reports denominated in either tokens or fiat. Only `account` and `tag` modes are supported.

Example: Read `account` grouped reports from ` _histout/account` and produce a new `_histout/balances.csv` report.

```sh
python -m history.summarizer --input _histout/account --output _histout/balances.csv --mode account
```

### reconciler

_reconciles an account balance table with a network_

Compares the account balances in an account balance table with live network balances.

Example: Compare the balances in `_histout/balances.csv` with the `spot` network balances reported by the network described in `templates/symbol.mainnet.yaml`.

```sh
python -m history.reconciler --input _histout/balances.csv --resources templates/symbol.mainnet.yaml --mode spot
```

> :warning: This will only succeed when _all_ balances have been downloaded.
