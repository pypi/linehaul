default:
	@echo "Call a specific subcommand"
	@exit 1


tests:
	docker-compose run --rm linehaul py.test $(T) $(TESTARGS)


.PHONY: default tests
