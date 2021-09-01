#!/usr/bin/env bash

rm -rf dist/
mkdir dist/
cp -rf db.sqlite3 user oss objects common buckets account templates static dist/
#pip3 freeze > x.txt
pip3 install -r requirement.txt --target dist/
#rm -f x.txt
shiv --site-packages dist --compressed -p '/usr/bin/env python3' -o oss.pyz -e oss.main --compile-pyc

