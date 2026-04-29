IMAGE_NAME ?= intelligence-hub
PORT ?= 8501
ENV_FILE ?= .env
MARKET ?= all
FOLDER ?= market_forms
RESPONSES ?= market_forms
OUTFILE ?= utm_consolidated.xlsx
ADDRESSBOOK ?= UTM_data/PHD_Local_Market_Addressbook.csv
DEADLINE ?= Friday, 09 May 2026
CC ?=

.PHONY: docker-build docker-run docker-run-mount docker-clean report-pdf media-spend-flat campaign-join utm-forms utm-consolidate utm-email-drafts cluster-analysis cluster-slide cluster-all

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

activate-venv:
	.\venv\Scripts\Activate.ps1

# Generate structured UTM response forms per market
# Usage:
#   make utm-forms MARKET=all FOLDER=market_forms_apr
#   make utm-forms MARKET=PCGB FOLDER=market_forms_pcgb
utm-forms:
	./UTM_data/run_utm_market_forms.sh generate "$(MARKET)" "$(FOLDER)"

# Consolidate completed market forms into one workbook
# Usage:
#   make utm-consolidate RESPONSES=market_forms_apr OUTFILE=utm_consolidated_apr.xlsx
utm-consolidate:
	./UTM_data/run_utm_market_forms.sh consolidate "$(RESPONSES)" "$(OUTFILE)"

# Build .eml drafts per market form in folder
# Usage:
#   make utm-email-drafts FOLDER=market_forms_apr ADDRESSBOOK=UTM_data/PHD_Local_Market_Addressbook.csv DEADLINE="Friday, 09 May 2026" CC="a@x.com;b@y.com"
utm-email-drafts:
	./.venv/bin/python UTM_data/build_market_email_drafts.py --forms-folder "UTM_data/$(FOLDER)" --addressbook-csv "$(ADDRESSBOOK)" --deadline "$(DEADLINE)" --cc "$(CC)"

# Run market clustering analysis using reverse-funnel targets
cluster-analysis:
	./.venv/bin/python budget_setting/run_market_cluster_analysis.py

# Build market cluster recommendation slide (.pptx) from latest outputs
cluster-slide:
	./.venv/bin/python budget_setting/build_market_cluster_slide.py

# Run full pipeline: analysis outputs + slide
cluster-all: cluster-analysis cluster-slide