ROOT_DIR:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))


default:
	docker build -t linehaul-build .
	docker run --rm -v $(ROOT_DIR):/usr/local/src/linehaul -it linehaul-build \
		cargo build --release --target x86_64-unknown-linux-musl
	zip -j ./target/x86_64-unknown-linux-musl/release/bootstrap.zip \
			 ./target/x86_64-unknown-linux-musl/release/bootstrap


.PHONY: default
