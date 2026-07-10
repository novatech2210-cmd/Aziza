# Build Instructions

## Docker Build
`docker compose -f configs/docker/docker-compose.yml build`

## Frontend Build
`cd frontend && npm install && npm run build`

## Backend Environment
`python3.12 -m venv venv312`
`source venv312/bin/activate`
`pip install -r requirements.txt`

## Training Environment
Use specific `training/requirements-train.txt` to include `bitsandbytes`, `peft`, `trl`.
