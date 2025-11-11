.PHONY: test-ret11

test-ret11:
	python3 scripts/generate_test_files.py
	python3 finalize_pipeline.py
	pytest -q
