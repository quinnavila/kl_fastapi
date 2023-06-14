run:
	uvicorn app.main:app
dev:
	uvicorn app.main:app --reload
test:
	pytest -vv app/ .
linter:
	ruff app/
build-docker:
	docker build -t kl-fastapi-app:v1 .
run-docker:
	docker run -p 8000:8000 kl-fastapi-app:v1
