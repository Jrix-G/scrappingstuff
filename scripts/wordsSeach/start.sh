#!/bin/bash

xhost +
source .venv/bin/activate
xvfb-run -a python main.py
