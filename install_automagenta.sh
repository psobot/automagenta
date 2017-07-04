#!/bin/bash

# Automagenta Install Script

curl https://github.com/psobot/automagenta > /usr/local/bin/automagenta
chmod +x /usr/local/bin/automagenta

pip install boto3
brew install s3cmd
