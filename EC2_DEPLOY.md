# EC2 Deployment

This deploys the verified local/demo mode. It uses the bundled telemetry CSV and SOP and does not require cloud credentials.

For a managed alternative to EC2, the repository includes `render.yaml`. Connect the repository to Render and create the web service from that blueprint.

## 1. Create the EC2 instance

Use Amazon Linux 2023, Ubuntu 22.04+, or another Docker-capable Linux AMI. In the instance security group, allow:

- TCP 22 from your own IP for SSH
- TCP 8501 from your own IP for the dashboard

Do not expose port 8501 to `0.0.0.0/0` for a production deployment. Put the app behind HTTPS and an authenticated reverse proxy instead.

## 2. Install Docker

On Amazon Linux 2023:

```bash
sudo dnf update -y
sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

Reconnect over SSH after the group change.

## 3. Copy and start the application

From the repository directory on the EC2 instance:

```bash
docker build -t cold-chain-logistics .
docker run -d \
  --name cold-chain-logistics \
  --restart unless-stopped \
  -p 8501:8501 \
  cold-chain-logistics
```

Open `http://EC2_PUBLIC_IP:8501` from an allowed client IP.

## 4. Check the service

```bash
docker ps
docker logs --tail 100 cold-chain-logistics
``` 

The container health endpoint is `/_stcore/health`.

## Live integrations

The image intentionally runs without secrets. To enable SQL Server, Pinecone, or a cloud LLM, create a private `.env` from `.env.example` and pass it at runtime:

```bash
docker run -d \
  --name cold-chain-logistics \
  --restart unless-stopped \
  --env-file .env \
  -p 8501:8501 \
  cold-chain-logistics
```

Never commit `.env` or place credentials directly in the Dockerfile.