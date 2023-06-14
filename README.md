# kl_fastapi

FastAPI server using SQLite database as a cache.

[Notebook](story.ipynb) showing functionality


## Steps to Run


### Local Installation
1. Install the required dependencies by running `pip install -r requirements.txt`.
2. Run the application using the command `make run`.

### Docker Installation
1. Build the Docker image by running `docker build -t <image-name> .`.
2. Run the Docker container using the command `docker run -p <host-port>:<container-port> <image-name>`.

## Basic functionality
- [x] GET /lookup/{vin}
- [x] DELETE /remove/{vin}
- [x] GET /export

## Code quality, error handling, testing, documentation
- [x] Linted with ruff
- [x] Exception handling
- [x] Basic logging
- [x] Docstrings
- [x] Testing with pytest
- [] More tests for concurrency, more error handling and edge cases
- [x] Dockerfile
- [] Opentelemetry 
- [] Github actions deployment workflow

## Evaluation Criteria
- [] Basic functionality
- [] Code quality
- [] Error handling
- [] Documentation (readme/comments/tests)
- [] Ability to explain your implementation decisions