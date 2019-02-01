FROM rust:1.32.0-slim

# Install our tooling for cross compiling with MUSL libc.
RUN set -x \
    && apt-get update \
    && apt-get install -y musl-tools perl-modules make \
    && rm -rf /var/lib/apt/lists/*

# Install our rust targets
RUN rustup target add x86_64-unknown-linux-musl

# Set our working directory to where we mount our development directory.
WORKDIR /usr/local/src/linehaul
