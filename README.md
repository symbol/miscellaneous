# Miscellany

### check NEM balances

Prints balance and last harvest information for a set of NIS1 and/or Symbol accounts.

Example: load accounts and nodes from `./templates` and print all NIS1 accounts with tag `group` and all Symbol accounts with tag `sink`.

```sh
python -m health.checkNemBalances --resources ./templates --nis-groups group --sym-groups sink
```
Options
 * `--use-names`: identify accounts by their friendly names in output
 * `--show_zero_balances`: show all groups that have zeroed balances (hidden by default)
