# syntax=docker/dockerfile:experimental

# Build stage: Install yarn dependencies
# ===
FROM node:18 AS build-frontend
WORKDIR /code
COPY . /code
RUN yarn install
RUN yarn run build-js
RUN yarn run build-css

# Build stage: Install python dependencies
# ===
FROM ubuntu:jammy AS base-dev
RUN apt update && apt install -y \
    python3 \
    python3-pip \
    python3-setuptools
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . /code
WORKDIR /code

# Build the production image
# ===
FROM ubuntu:jammy

# Set up environment
ENV LANG C.UTF-8
WORKDIR /srv


# Install python and import python dependencies
RUN apt-get update && apt-get install --no-install-recommends --yes python3 python3-setuptools python3-lib2to3 python3-pkg-resources ca-certificates libsodium-dev
ENV PATH="/root/.local/bin:${PATH}"

# Copy python dependencies
COPY --from=base-dev /root/.local/lib/python3.10/site-packages /root/.local/lib/python3.10/site-packages
COPY --from=base-dev /root/.local/bin /root/.local/bin

# COPY necessary all files but remove those that are not required
COPY . .
RUN rm -rf package.json yarn.lock .babelrc webpack.config.js requirements.txt
COPY --from=build-css /srv/static/css static/css
COPY --from=build-js /srv/static/js static/js

# Set build ID
ARG BUILD_ID
ENV TALISKER_REVISION_ID "${BUILD_ID}"
