import argparse
import asyncio
import json
import os
from binascii import unhexlify

import aiohttp
import nest_asyncio
import pandas as pd
from tqdm.asyncio import tqdm

from block.extractor import public_key_to_address

nest_asyncio.apply()


# list of all of the nodes we're going to spam with GET requests
nodes = [
    'ngl-dual-001.symbolblockchain.io',
    'ngl-dual-101.symbolblockchain.io',
    'ngl-dual-201.symbolblockchain.io',
    'ngl-dual-301.symbolblockchain.io',
    'ngl-dual-401.symbolblockchain.io',
    'ngl-dual-501.symbolblockchain.io',
    'ngl-dual-601.symbolblockchain.io',
]


async def _get_tx_info(session, node, tx_id, max_failures=5):
    """Helper function for making a single tx info API request"""
    failures = 0
    while failures < max_failures:
        try:
            async with session.get(f'http://{node}:3000/transactions/confirmed/{tx_id}') as resp:
                return await resp.json()
        except aiohttp.ClientConnectionError:
            await(asyncio.sleep(0.25))
            failures += 1


async def get_nember_data(node, sleep, max_failures=5, max_height=1000000):
    """Search for mosaic definitions that match the nember pattern, then record NFT details"""
    failures = 0
    page = 1
    height = 0
    pbar = tqdm(total=max_height)
    tasks = []
    transactions = []
    while failures < max_failures:
        try:
            async with aiohttp.ClientSession() as session:
                while True:
                    async with session.get(f'http://{node}:3000/transactions/confirmed?type=16961&pageSize=100&pageNumber={page}') as resp:
                        aggregate_tx = await resp.json()
                    if len(aggregate_tx['data']) == 0:
                        break
                    for txn in aggregate_tx['data']:
                        tasks.append(asyncio.ensure_future(_get_tx_info(session, node, txn['id'])))
                        await asyncio.sleep(sleep)
                    pbar.update(int(aggregate_tx['data'][-1]['meta']['height']) - height)
                    height = int(aggregate_tx['data'][-1]['meta']['height'])
                    page += 1
                pbar.close()
                transactions = await tqdm.gather(tasks)
                failures = max_failures + 1
        except KeyError:
            print(aggregate_tx)
        except aiohttp.ClientConnectionError:
            # connection dropped
            failures += 1
            await asyncio.sleep(sleep)
    if failures == max_failures:
        pbar.close()
    return transactions


async def get_mosaic_tx(mosaic_id, session, node, sleep, max_failures=50000):
    """Helper function for making a single tx info API request"""
    failures = 0
    page = 1
    transactions = []
    while failures < max_failures:
        try:
            while True:
                async with session.get(
                        f'http://{node}:3000/transactions/confirmed?pageSize=100&pageNumber={page}&transferMosaicId={mosaic_id}') as resp:
                    matching_tx = await resp.json()
                if len(matching_tx['data']) == 0:
                    break
                transactions.extend(matching_tx['data'])
                if len(matching_tx['data']) < 100:
                    break
                page += 1
                await asyncio.sleep(sleep)
            return transactions
        except aiohttp.ClientConnectionError:
            # connection dropped
            failures += 1
            await asyncio.sleep(sleep)


async def get_nember_tx(mosaic_ids, node, sleep, max_failures=5):
    """Search for NFT transactions"""
    failures = 0
    transactions = []
    tasks = []
    while failures < max_failures:
        try:
            async with aiohttp.ClientSession(read_timeout=0) as session:
                for mosaic_id in tqdm(mosaic_ids):
                    tasks.append(asyncio.ensure_future(get_mosaic_tx(mosaic_id, session, node, sleep)))
                    await asyncio.sleep(sleep)
                transactions = await tqdm.gather(tasks)
                failures = max_failures
        except aiohttp.ClientConnectionError:
            # connection dropped
            failures += 1
            await asyncio.sleep(sleep)
    return transactions


def main(args):
    # pylint: disable=too-many-locals, too-many-branches

    loop = asyncio.get_event_loop()
    # should request max height from API; remove parameter
    transactions = loop.run_until_complete(get_nember_data(nodes[0], 1/args.request_limit, max_height=args.max_height))

    nft_mosaics = []
    platform_tx = []
    for txn in transactions:
        if len(txn['transaction']['transactions']) == 4:
            flag = False
            for sub_tx in txn['transaction']['transactions']:
                if sub_tx['transaction']['type'] == 0x4154:
                    if 'message' in sub_tx['transaction'] and 'NEMBER.ART' in unhexlify(sub_tx['transaction']['message']).decode('UTF-8'):
                        flag = True
            if flag:
                gen_tx = [x for x in txn['transaction']['transactions'] if x['transaction']['type'] == 0x414d]
                meta_tx = [x for x in txn['transaction']['transactions'] if x['transaction']['type'] == 0x4244]
                supply_tx = [x for x in txn['transaction']['transactions'] if x['transaction']['type'] == 0x424d]
                if any([len(x) != 1 for x in [gen_tx, meta_tx, supply_tx]]):
                    platform_tx.append(txn)
                    continue
                gen_tx = gen_tx[0]
                meta_tx = meta_tx[0]
                supply_tx = supply_tx[0]
                try:
                    metadata = json.loads(unhexlify(meta_tx['transaction']['value']).decode('UTF-8'))
                    name = metadata['data']['meta']['name']
                except json.JSONDecodeError:  # some metadata is double-encoded
                    metadata = json.loads(unhexlify(unhexlify(meta_tx['transaction']['value']).decode('UTF-8')).decode('UTF-8'))
                    name = metadata['data']['meta']['name']
                nft_mosaics.append({
                    'name': name,
                    'id': gen_tx['transaction']['id'],
                    'supply': int(supply_tx['transaction']['delta']),
                    'height': int(txn['meta']['height']),
                    'mint_address': public_key_to_address(unhexlify(gen_tx['transaction']['signerPublicKey'])),
                    'metadata_key': meta_tx['transaction']['scopedMetadataKey'],
                    'metadata': metadata
                })

    print(f'NFTs identified: {len(nft_mosaics)}')
    print(f'nember platform TX identified: {len(platform_tx)}')

    nft_df_list = []
    for nft in nft_mosaics:
        nft_df_list.append({
            'name': nft['name'],
            'id': nft['id'],
            'minted_height': nft['height'],
            'mint_address': nft['mint_address'],
            'metadata_key': nft['metadata_key'],
            'ipfs': nft['metadata']['data']['media']['ipfs'],
            'description': nft['metadata']['data']['meta']['description']
        })

    nft_df = pd.DataFrame(nft_df_list)
    nft_df.to_csv(os.path.join(args.output, args.info_save_path))

    # Extract NFT transactions. Takes at least a couple hours due to constraints on the node side.
    nft_ids = set(nft_df['id'].values)
    nft_tx = loop.run_until_complete(get_nember_tx(list(nft_ids), nodes[0], 1/args.request_limit))

    nft_tx_df_list = []
    for transactions in nft_tx:
        for sub_tx in transactions:
            height = sub_tx['meta']['height']
            sender = public_key_to_address(unhexlify(sub_tx['transaction']['signerPublicKey']))
            recipient = sub_tx['transaction']['recipientAddress']
            for mosaic in sub_tx['transaction']['mosaics']:
                if mosaic['id'] in nft_ids and int(mosaic['amount']) == 1:
                    nft_tx_df_list.append({
                        'height': height,
                        'id': mosaic['id'],
                        'sender': sender,
                        'recipient': recipient
                    })

    nft_tx_df = pd.DataFrame(nft_tx_df_list)
    nft_tx_df.to_csv(os.path.join(args.output, args.tx_save_path))


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=str, default='resources', help='directory to dump output')
    parser.add_argument('--info_save_path', type=str, default='nember_mosaic_data.csv', help='file to write the nft information table to')
    parser.add_argument('--tx_save_path', type=str, default='nember_transactions.csv', help='file to write nft transaction log to')
    parser.add_argument('--request_limit', type=float, default=59.0, help='maximum reqests to make per second')
    parser.add_argument('--max_height', type=float, default=637000, help='target height to calibrate progress bar; DOES NOT affect data')

    parsed_args = parser.parse_args()
    main(parsed_args)
