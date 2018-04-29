#!/bin/bash

set -eux

EC2_SSH="ssh ec2-user@$EC2_HOST"

$EC2_SSH rm -Rf hl
$EC2_SSH mkdir -p hl

for dep in $(cat requirements.txt); do
  $EC2_SSH pip install $dep -t hl
done

rm -Rf /tmp/dist
mkdir /tmp/dist

$EC2_SSH 'tar -C hl -cf temp.tar $(ls hl)'
scp ec2-user@$EC2_HOST:temp.tar /tmp/dist/

cp lambda_function.py /tmp/dist/

cd /tmp/dist
tar -xf temp.tar
rm temp.tar

zip -r ~/Downloads/00000.zip *
