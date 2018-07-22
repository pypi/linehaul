default:
	@echo "Call a specific subcommand"
	@exit 1


tests:
	docker-compose run --rm linehaul py.test --cov linehaul --cov-report term-missing:skip-covered $(T) $(TESTARGS)


.PHONY: default tests
