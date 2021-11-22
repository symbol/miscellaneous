import argparse
from collections import namedtuple
from datetime import datetime

from client.CoinGeckoClient import CoinGeckoClient
from client.ResourceLoader import create_blockchain_api_client, load_resources

NetworkDescriptor = namedtuple('NetworkDescriptor', [
    'friendly_name', 'resources_name', 'blocks_per_day', 'row_view_factory'
])
AccountRowView = namedtuple('AccountRowView', ['address', 'public_key', 'account_type', 'balance',  'importance', 'percent_vested'])
NetworkPrinterOptions = namedtuple('NetworkPrinterOptions', ['use_friendly_names', 'show_zero_balances'])


# region descriptors

nem_network_descriptor = NetworkDescriptor(**{
    'friendly_name': 'NEM',
    'resources_name': 'nem.mainnet',
    'blocks_per_day': 1440,

    'row_view_factory': lambda account_info: AccountRowView(**{
        'address': account_info.address,
        'public_key': account_info.public_key,
        'account_type': account_info.remote_status,

        'balance': account_info.balance,
        'importance': account_info.importance,
        'percent_vested': 0 if not account_info.balance else account_info.vested_balance / account_info.balance
    })
})


symbol_network_descriptor = NetworkDescriptor(**{
    'friendly_name': 'SYMBOL',
    'resources_name': 'symbol.mainnet',
    'blocks_per_day': 2880,

    'row_view_factory': lambda account_info: AccountRowView(**{
        'address': account_info.address,
        'public_key': account_info.public_key,
        'account_type': account_info.remote_status,

        'balance': account_info.balance,
        'importance': account_info.importance,
        'percent_vested': None
    })
})

# endregion

# region NetworkPrinter


class NetworkPrinter:
    def __init__(self, network_descriptor, resources, network_printer_options):
        self.show_zero_balances = network_printer_options.show_zero_balances
        self.use_friendly_names = network_printer_options.use_friendly_names

        self.friendly_name = network_descriptor.friendly_name
        self.row_view_factory = network_descriptor.row_view_factory

        self.resources = resources
        self.api_client = create_blockchain_api_client(self.resources)

        self.blocks_per_day = network_descriptor.blocks_per_day
        self.chain_height = self.api_client.get_chain_height()

    def print_all(self, group_names, token_price):
        for group_name in group_names:
            group_description = f'[{self.friendly_name} @ {self.chain_height}] \033[36m{group_name.upper()}\033[39m ACCOUNTS'

            total_balance, num_matching_accounts = self._print_accounts(
                [account_descriptor.address for account_descriptor in self.resources.accounts.find_all_by_role(group_name)],
                group_description)

            if not total_balance and not self.show_zero_balances:
                continue

            if not num_matching_accounts:
                self._print_header(group_description)

            self.print_hline()
            total_balance_usd = int(total_balance) * float(token_price)
            print(f'{total_balance:,.6f} (~${total_balance_usd:,.2f} USD)')
            self.print_hline()
            print()

    def _print_accounts(self, addresses, description):
        account_row_views = [self.row_view_factory(self.api_client.get_account_info(address)) for address in addresses]

        has_printed_header = False
        total_balance = 0
        for account_view in account_row_views:
            if not account_view.balance and not self.show_zero_balances:
                continue

            if not has_printed_header:
                self._print_header(description)
                has_printed_header = True

            formatted_last_harvest_height = self._get_formatted_last_harvest_height(account_view.address)

            print('| {:<40} |  {}  | {} | {:.5f} | {} | {:>20,.6f} | {:>3} |'.format(  # pylint: disable=consider-using-f-string
                self._get_account_display_name(account_view.address),
                ' ' if not account_view.public_key else 'X',
                account_view.account_type[0:4].upper(),
                round(account_view.importance, 5),
                formatted_last_harvest_height,
                account_view.balance,
                'N/A' if account_view.percent_vested is None else round(account_view.percent_vested * 100)
            ))

            total_balance += account_view.balance

        return (total_balance, len(account_row_views))

    def _print_header(self, description):
        # 50 to account for ansi escape color codes
        balance_header_text = 'Balance'
        print(f'| {description:<50} | PK  | TYPE | IMPORTA |  HARVEST HEIGHT  | {balance_header_text:<20} | V % | ')
        self.print_hline()

    def _get_account_display_name(self, address):
        if not self.use_friendly_names:
            return str(address)

        account_descriptor = self.resources.accounts.find_by_address(address)
        return account_descriptor.name if account_descriptor else str(address)

    def _get_formatted_last_harvest_height(self, address):
        harvest_snapshots = self.api_client.get_harvests(address)
        last_harvest_height = 0 if not harvest_snapshots else harvest_snapshots[0].height
        last_harvest_height_description, color_name = self._last_harvest_height_to_string(last_harvest_height)

        formatted_string = f'{last_harvest_height:>7} {last_harvest_height_description:>8}'
        if not color_name:
            return formatted_string

        color_codes = {'blue': 34, 'red': 31, 'yellow': 33}
        return f'\033[{color_codes[color_name]}m{formatted_string}\033[39m'

    def _last_harvest_height_to_string(self, last_harvest_height):
        if 0 == last_harvest_height:
            return ('NEVER', 'blue')

        blocks_since_harvest = self.chain_height - last_harvest_height
        blocks_per_hour = self.blocks_per_day // 24
        blocks_per_minute = blocks_per_hour // 60

        if blocks_since_harvest < 100 * blocks_per_minute:
            minutes = blocks_since_harvest / blocks_per_minute
            return (f'~ {minutes:5.2f}M', None)

        if blocks_since_harvest < 100 * blocks_per_hour:
            hours = blocks_since_harvest / blocks_per_hour
            color_name = 'red' if hours >= 24 else 'yellow'
            return (f'~ {hours:5.2f}H', color_name)

        days = blocks_since_harvest / self.blocks_per_day
        return (f'~ {days:5.2f}D', 'red')

    @staticmethod
    def print_hline():
        print('-----' * 23)


# endregion


def main():
    parser = argparse.ArgumentParser(description='check balances of multiple accounts in a network')
    parser.add_argument('--resources', help='directory containing resources', required=True)
    parser.add_argument('--groups', help='account groups to include', type=str, nargs='+')
    parser.add_argument('--use-names', help='display friendly account names', action='store_true')
    parser.add_argument('--show-zero-balances', help='show zero balance accounts', action='store_true')
    args = parser.parse_args()

    resources = load_resources(args.resources)

    coin_gecko_client = CoinGeckoClient()
    token_price = coin_gecko_client.get_price_spot(resources.ticker_name, 'usd')

    print(f' UTC Time: {datetime.utcnow()}')
    print(f'{resources.currency_symbol.upper()} Price: {token_price:.6f}')
    print()

    network_printer_options = NetworkPrinterOptions(**{
        'use_friendly_names': args.use_names,
        'show_zero_balances': args.show_zero_balances
    })

    network_descriptor = {'nem': nem_network_descriptor, 'symbol': symbol_network_descriptor}[resources.friendly_name]

    printer = NetworkPrinter(network_descriptor, resources, network_printer_options)
    printer.print_all(args.groups, token_price)


if '__main__' == __name__:
    main()
