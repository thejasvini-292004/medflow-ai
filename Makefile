# MedFlow AI — common commands
.PHONY: help install bootstrap db index app test lint clean docker-build docker-run

help:
	@echo "MedFlow AI"
	@echo "  make install       Install Python dependencies"
	@echo "  make bootstrap     Build the SQLite DB and the Chroma index"
	@echo "  make db            (Re)generate the synthetic hospital database"
	@echo "  make index         (Re)build the protocol vector index"
	@echo "  make app           Launch the Streamlit UI"
	@echo "  make test          Run the pytest suite (offline, no API keys)"
	@echo "  make docker-build  Build the Docker image"
	@echo "  make docker-run    Run the container (reads .env)"
	@echo "  make clean         Remove generated data + caches"

install:
	pip install -r requirements.txt

bootstrap:
	python -m scripts.bootstrap

db:
	python -m src.medflow.db.generate_data

index:
	python -m src.medflow.knowledge.build_index

app:
	streamlit run src/medflow/app.py

test:
	pytest -q

docker-build:
	docker build -t medflow-ai:latest .

docker-run:
	docker run --rm -p 8501:8501 --env-file .env medflow-ai:latest

clean:
	rm -rf data/medflow.db data/chroma __pycache__ .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
