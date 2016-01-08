default:
	@echo "Must call a specific subcommand"
	@exit 1

tests:
	coverage run -m pytest --strict $(T) $(TESTARGS)
	coverage report -m

lint:
	flake8 .

.PHONY: default tests lint
