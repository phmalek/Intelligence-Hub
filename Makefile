IMAGE_NAME ?= intelligence-hub
PORT ?= 8501
ENV_FILE ?= .env

.PHONY: docker-build docker-run docker-run-mount docker-clean

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
