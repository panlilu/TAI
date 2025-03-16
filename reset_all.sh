#!/bin/bash

rm -rf ./data/uploads/*
./reset_db.sh
./seed_db.sh