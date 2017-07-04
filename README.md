# Automagenta

A tiny script to run TensorFlow programs on GPU instances in the cloud.

&copy; 2017 Peter Sobot (github@petersobot.com)

---

## What is this?

`automagenta` is a helper that allows people to run *TensorFlow apps* that
could benefit from [fast GPUs in Amazon's Cloud](https://aws.amazon.com/ec2/Elastic-GPUs/)
with a minimum of fuss. With very little configuration and
only one command, an instance will be started, and local code and data made
available for use. Think of this like [AWS
Lambda](https://aws.amazon.com/lambda/), but for machine learning apps that
need GPUs, and only for speeding up development.

As the name suggests, this script was built for use with [the Magenta
project](https://github.com/tensorflow/magenta), Google's music and art
generation framework on top of TensorFlow. It could easily be adapted to other
frameworks and for other purposes.

**IMPORTANT NOTE**: This script connects to Amazon Web Services and creates
instances, often expensive GPU-enabled instances. By using `automagenta` and
related software, you accept full responsibility and risk for any charges that
occur on your AWS account. By installing `automagenta`, you acknowledge that
its use will incur charges on your AWS account and that those charges may be
substantial if left unattended. I give no warranties as to the correctness of
this software, and will not be held liable for charges that may arise from its
use.

## Why use this over my own instance?

 - You want something simple that feels like local development.
 - You don't want to have to worry about instance management or installation.
 - You want instances that will automatically shut down when not in use.
 - You want your machine learning training to happen 12x as fast as on your MacBook Pro.

## Why not use &lt;x&gt;?

You're right, someone else has probably done this better. This was an attempt
to build something dead simple to use, targeted at people who are more
interested in experimenting with the machine learning tools than administering
Linux servers. (Indeed, this tool was built because non-programmers wanted to
try out Magenta.)

## How do I use this?

### Assuming you're on macOS:

 1. Ensure you already have a working Python installation, `pip` and `brew` installed.
 1. Install `automagenta` by running this (very insecure, but whatever) command in your Terminal:
    ```
    curl https://raw.githubusercontent.com/psobot/automagenta/master/install-macos.sh | bash
    ```
 1. Ensure you have an Amazon Web Services account created and you have an `ACCESS_KEY_ID` and `SECRET_ACCESS_KEY` configured ([as per the `boto` documentation](http://boto3.readthedocs.io/en/latest/guide/configuration.html)).
     - Amazon has good [documentation on creating an account here](http://docs.aws.amazon.com/lambda/latest/dg/setup.html).
     - Amazon also has good [documentation on configuring your access keys](http://docs.aws.amazon.com/lambda/latest/dg/setup-awscli.html)

 1. (Optional, but strongly recommended) [Create a Billing Alarm](http://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-alarms.html) on your AWS account just in case your instances don't terminate for whatever reason.
     - In case something goes wrong, be sure you know how to [terminate instances on your account](http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/terminating-instances.html).

 1. Wherever you write your code, create a new directory for each `magenta` experiment you want to run in the cloud. Give this directory a distinctive name, as you may run multiple of these tests/experiments at the same time. Each directory corresponds to an instance. (At time of writing, the cheapest GPU instance costs $0.90 USD/hour.)
 1. Put all of the files you need in this directory, and put the commands you want to run in a file called `run.sh`.
 1. Run `automagenta <directory_name>` (without `<` and `>`), where `<directory_name>` is the name of your directory.
 1. `automagenta` will upload your directory to the instance, run `run.sh`, and download the results.
 1. The instance will automatically shut off after it has been running for 55 minutes, unless it is still running `run.sh`, in which case it will remain running until it finishes.

## Why are so many shortcuts/security holes present in the code?

This was written quickly to solve a pressing need for people who don't fully
understand the implications of web server security, and for whom the threat
model and worst case scenario is pretty banal. If you want this to be more
secure, please be my guest and submit a PR.

## Who built this and what is this licensed under?

`automagenta` was written on July 3rd, 2017 by Peter Sobot
(github@petersobot.com, [@psobot](https://twitter.com/psobot)). It is licensed
under the permissive MIT License:

```
The MIT License

Copyright (c) 2017 Peter Sobot. http://petersobot.com

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```
