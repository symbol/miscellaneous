#!/bin/bash

python3 -m treasury.app --proxy 'http://0.0.0.0:8080::https://magicmouth.monster/treasury/' --base_path '/treasury/' --serve --host '0.0.0.0'