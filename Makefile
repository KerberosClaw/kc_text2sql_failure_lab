.PHONY: db eval eval-model eval-cli gallery test

db:          ## rebuild demo.db (deterministic, seeded)
	.venv/bin/python -m failure_lab.db_gen || python3 -m failure_lab.db_gen

eval:        ## run both mocks + refresh gallery data (no API key)
	.venv/bin/python -m failure_lab.runner --provider mock-naive || python3 -m failure_lab.runner --provider mock-naive
	.venv/bin/python -m failure_lab.runner --provider mock-oracle || python3 -m failure_lab.runner --provider mock-oracle
	.venv/bin/python -m failure_lab.runner --export-web || python3 -m failure_lab.runner --export-web

eval-model:  ## score a real model: FLAB_MODEL=... FLAB_API_KEY=... [FLAB_BASE_URL=...] make eval-model
	.venv/bin/python -m failure_lab.runner --provider openai || python3 -m failure_lab.runner --provider openai
	.venv/bin/python -m failure_lab.runner --export-web || python3 -m failure_lab.runner --export-web

eval-cli:    ## score a local agent CLI: FLAB_CLI_CMD="codex exec" FLAB_MODEL=codex make eval-cli
	.venv/bin/python -m failure_lab.runner --provider cli || python3 -m failure_lab.runner --provider cli
	.venv/bin/python -m failure_lab.runner --export-web || python3 -m failure_lab.runner --export-web

gallery:     ## serve the static gallery
	python3 -m http.server -d web 8080

test:
	.venv/bin/pytest -q || pytest -q
