#!/bin/bash

# Automagenta Install Script

curl https://raw.githubusercontent.com/psobot/automagenta/master/automagenta.py > /usr/local/bin/automagenta
chmod +x /usr/local/bin/automagenta

pip install boto3
brew install s3cmd
