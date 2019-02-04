ROOT_DIR:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))


default:
	docker build -t linehaul-build .
	docker run --rm -v $(ROOT_DIR):/usr/local/src/linehaul -it linehaul-build \
		cargo build --bin bootstrap --release --target x86_64-unknown-linux-musl
	rm ./target/x86_64-unknown-linux-musl/release/bootstrap.zip
	zip -j ./target/x86_64-unknown-linux-musl/release/bootstrap.zip \
			 ./target/x86_64-unknown-linux-musl/release/bootstrap

deploy: default
	aws --profile psf-prod s3 cp ./target/x86_64-unknown-linux-musl/release/bootstrap.zip \
		s3://pypi-lambdas/linehaul


.PHONY: default
