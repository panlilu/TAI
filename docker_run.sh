#!/bin/bash

docker run --env-file .env -p 8000:8000 -v ./data:/app/data tai-app 