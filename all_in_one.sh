#!/usr/bin/env bash

rm -rf dist/
mkdir dist/
cp -rf __main__.py db.sqlite3 user oss objects common buckets account dist/
pip freeze > x.txt
pip3 install -r x.txt --target dist/
rm -f x.txt
shiv --site-packages dist --compressed -p '/usr/bin/env python3' -o oss.pyz -e oss.main

