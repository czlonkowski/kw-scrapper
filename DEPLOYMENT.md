# EKW Scraper Deployment Guide

This guide provides instructions for deploying the EKW Scraper application using Docker and GitHub Container Registry.

## Prerequisites

- Git
- Docker and Docker Compose
- GitHub account with access to GitHub Container Registry (GHCR)

## Multi-Architecture Support

The EKW Scraper Docker image is built for multiple architectures:
- `linux/amd64` (x86_64) - Standard Intel/AMD processors
- `linux/arm64` (aarch64) - ARM-based processors like Apple M1/M2, AWS Graviton, and Raspberry Pi 4

This allows you to run the application on various platforms without modification.

## Local Deployment with Docker Compose

1. Clone the repository:
   ```bash
   git clone https://github.com/czlonkowski/kw-scrapper.git
   cd kw-scrapper
   ```

2. Create a `.env` file with your configuration:
   ```
   ekw_portal_url=https://przegladarka-ekw.ms.gov.pl/eukw_prz/KsiegiWieczyste/wyszukiwanieKW?komunikaty=true&kontakt=true&okienkoSerwisowe=false
   MAX_CONCURRENT=5
   LOG_LEVEL=INFO
   ```

3. Build and start the containers:
   ```bash
   docker-compose up -d
   ```

4. Access the API at `http://localhost:8000/docs`

## GitHub Container Registry Deployment

The EKW Scraper includes GitHub Actions workflows to automatically build and publish Docker images to GitHub Container Registry.

### Setup GitHub Container Registry

1. Ensure your GitHub repository has the appropriate permissions to publish packages.

2. The workflow will automatically run when you push to the `main` branch or create a tag with the format `v*` (e.g., `v1.0.0`).

3. To manually trigger a build and publish:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

### Using the Published Image

1. Pull the image from GitHub Container Registry:
   ```bash
   docker pull ghcr.io/czlonkowski/kw-scrapper:latest
   ```

2. Run the container:
   ```bash
   docker run -d -p 8000:8000 \
     -e ekw_portal_url=https://przegladarka-ekw.ms.gov.pl/eukw_prz/KsiegiWieczyste/wyszukiwanieKW?komunikaty=true&kontakt=true&okienkoSerwisowe=false \
     -e MAX_CONCURRENT=5 \
     -e LOG_LEVEL=INFO \
     ghcr.io/czlonkowski/kw-scrapper:latest
   ```

## Production Deployment Considerations

For production deployments, consider the following:

1. **Enable Redis Caching**: Uncomment the Redis service in `docker-compose.yml` to enable caching for frequently accessed KW numbers.

2. **Set Up HTTPS**: Use a reverse proxy like Nginx or Traefik to handle HTTPS termination.

3. **Implement Rate Limiting**: Configure rate limiting to prevent overloading the EKW portal.

4. **Monitoring**: Set up monitoring and alerting for the application.

5. **Backup Strategy**: Implement a backup strategy for any persistent data.

## Kubernetes Deployment

For Kubernetes deployment, you can use the provided Docker image with a Kubernetes manifest:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ekw-scraper
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ekw-scraper
  template:
    metadata:
      labels:
        app: ekw-scraper
    spec:
      containers:
      - name: ekw-scraper
        image: ghcr.io/czlonkowski/kw-scrapper:latest
        ports:
        - containerPort: 8000
        env:
        - name: ekw_portal_url
          value: "https://przegladarka-ekw.ms.gov.pl/eukw_prz/KsiegiWieczyste/wyszukiwanieKW?komunikaty=true&kontakt=true&okienkoSerwisowe=false"
        - name: MAX_CONCURRENT
          value: "5"
        - name: LOG_LEVEL
          value: "INFO"
        resources:
          limits:
            cpu: "1"
            memory: "1Gi"
          requests:
            cpu: "500m"
            memory: "512Mi"
        livenessProbe:
          httpGet:
            path: /api/scraper/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 30
---
apiVersion: v1
kind: Service
metadata:
  name: ekw-scraper
spec:
  selector:
    app: ekw-scraper
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
```

Apply this manifest with:
```bash
kubectl apply -f kubernetes-deployment.yaml
