IMAGE_NAME ?= intelligence-hub
PORT ?= 8501
ENV_FILE ?= .env

.PHONY: docker-build docker-run docker-run-mount docker-clean report-pdf media-spend-flat campaign-join

# Build Docker image

docker-build:
	docker build -t $(IMAGE_NAME) .

# Run container using env file
# Usage: make docker-run (reads $(ENV_FILE))

docker-run:
	docker run --rm -p $(PORT):8501 \
		--env-file $(ENV_FILE) \
		$(IMAGE_NAME)

# Run container with data volume mount and env file
# Usage: make docker-run-mount (reads $(ENV_FILE))

docker-run-mount:
	docker run --rm -p $(PORT):8501 \
		--env-file $(ENV_FILE) \
		-v "$(PWD)/pwc reports:/home/appuser/app/pwc reports" \
		$(IMAGE_NAME)

# Remove local image

docker-clean:
	docker rmi -f $(IMAGE_NAME)

# Build PDF from the markdown report
report-pdf:
	pandoc reports/close_the_gap_80k_iter_01.md \
		--resource-path=reports \
		--from markdown+implicit_figures \
		-o reports/close_the_gap_80k_iter_01.pdf

# Flatten media spend Excel into raw CSV (no filters)
media-spend-flat:
	python3 other_data/ctg_pre_01/flatten_media_spend_xlsx.py

# Build campaign performance with spend join
# Flags: --id --substring --token --fuzzy --id-min-length=4 --token-threshold=0.4 --fuzzy-threshold=0.75
campaign-join:
	python3 other_data/ctg_pre_01/build_campaign_performance_with_spend.py --id --substring --token --fuzzy --id-min-length 4
