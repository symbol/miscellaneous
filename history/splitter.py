import argparse
import datetime
import os
from pathlib import Path

from zenlog import log


def main():
    parser = argparse.ArgumentParser(
        description='filter csv file by date range',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--input', help='input directory', required=True)
    parser.add_argument('--output', help='output directory', required=True)
    parser.add_argument('--start-date', help='start date', required=True)
    parser.add_argument('--end-date', help='end date', default=datetime.date.today().isoformat())
    args = parser.parse_args()

    input_directory = Path(args.input)
    if not input_directory.exists():
        log.warn(f'input directory \'{args.input}\' does not exist')
        return

    output_directory = Path(args.output)
    if output_directory.exists():
        log.warn(f'output directory \'{args.output}\' already exists')
        return

    log.info('starting processing!')

    output_directory.mkdir(parents=True)

    start_date = datetime.date.fromisoformat(args.start_date)
    end_date = datetime.date.fromisoformat(args.end_date)

    for filename in os.listdir(input_directory):
        log.info(f'processing {filename}...')
        with open(input_directory / filename, 'rt', encoding='utf8') as infile:
            is_empty = True
            with open(output_directory / filename, 'wt', encoding='utf8') as outfile:
                input_lines = infile.readlines()
                outfile.write(input_lines[0])

                for line in input_lines[1:]:
                    timestamp = datetime.datetime.fromisoformat(line[:line.index(',')])
                    if timestamp.date() < start_date or timestamp.date() > end_date:
                        continue

                    outfile.write(line)
                    is_empty = False

            if is_empty:
                Path(output_directory / filename).unlink()


if '__main__' == __name__:
    main()
