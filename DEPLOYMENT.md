# Deployment Guide for MCP Server Mock Jivi

## Prerequisites
- Python 3.13+ (or Docker)
- OpenAI API key
- Environment variables configured

## Deployment Options

### Option 1: Docker (Recommended for Production)

#### Build and Run Locally
```bash
# Build image
docker build -t mcp-server-mock-jivi .

# Run container
docker run -d \
  -p 8000:8000 \
  -e OPENAI_API_KEY=your-key-here \
  -e MCP_SERVER_TOKEN=your-secret-token \
  --name mcp-server \
  mcp-server-mock-jivi
```

#### Using Docker Compose
```bash
# Create .env file
cat > .env << EOF
OPENAI_API_KEY=your-key-here
MCP_SERVER_TOKEN=your-secret-token
OPENAI_MODEL=gpt-4o-mini
LOG_LEVEL=INFO
EOF

# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Option 2: Direct Python (Development/Local)

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY=your-key-here
export MCP_SERVER_TOKEN=your-secret-token

# Run server
python main.py
```

### Option 3: Cloud Platforms

#### Railway
1. Install Railway CLI: `npm i -g @railway/cli`
2. Login: `railway login`
3. Initialize: `railway init`
4. Add environment variables in Railway dashboard
5. Deploy: `railway up`

#### Render
1. Connect GitHub repository
2. Create new Web Service
3. Set:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python main.py`
4. Add environment variables
5. Deploy

#### Heroku
```bash
# Install Heroku CLI, then:
heroku create your-app-name
heroku config:set OPENAI_API_KEY=your-key
heroku config:set MCP_SERVER_TOKEN=your-token
git push heroku main
```

#### AWS (ECS/Fargate)
1. Push Docker image to ECR
2. Create ECS task definition with environment variables
3. Deploy to Fargate or EC2

#### Google Cloud Run
```bash
gcloud builds submit --tag gcr.io/PROJECT-ID/mcp-server
gcloud run deploy mcp-server \
  --image gcr.io/PROJECT-ID/mcp-server \
  --platform managed \
  --region us-central1 \
  --set-env-vars OPENAI_API_KEY=your-key
```

#### Azure Container Instances
```bash
az container create \
  --resource-group myResourceGroup \
  --name mcp-server \
  --image mcp-server-mock-jivi \
  --dns-name-label mcp-server \
  --ports 8000 \
  --environment-variables OPENAI_API_KEY=your-key
```

### Option 4: VPS/Server (Ubuntu/Debian)

```bash
# SSH into server
ssh user@your-server

# Install Python and dependencies
sudo apt update
sudo apt install python3.13 python3-pip -y

# Clone repository
git clone your-repo-url
cd mcp_server_mock_jivi

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up systemd service
sudo nano /etc/systemd/system/mcp-server.service
```

Systemd service file (`/etc/systemd/system/mcp-server.service`):
```ini
[Unit]
Description=MCP Server Mock Jivi
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/mcp_server_mock_jivi
Environment="OPENAI_API_KEY=your-key"
Environment="MCP_SERVER_TOKEN=your-token"
Environment="PATH=/path/to/mcp_server_mock_jivi/venv/bin"
ExecStart=/path/to/mcp_server_mock_jivi/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable mcp-server
sudo systemctl start mcp-server
sudo systemctl status mcp-server
```

## Environment Variables

Required:
- `OPENAI_API_KEY` - Your OpenAI API key

Optional:
- `MCP_SERVER_TOKEN` - Auth token (default: "super-secret-token")
- `OPENAI_MODEL` - Model name (default: "gpt-4o-mini")
- `LOG_LEVEL` - Logging level (default: "INFO")
- `LOG_FILE` - Log file path (default: "server.log")
- `HOST` - Bind host (default: "0.0.0.0")
- `PORT` - Port number (default: 8000)

## Production Considerations

### Security
- ✅ Use HTTPS (nginx/Traefik reverse proxy)
- ✅ Set strong `MCP_SERVER_TOKEN`
- ✅ Restrict firewall rules
- ✅ Use secrets management (AWS Secrets Manager, etc.)

### Performance
- Use `gunicorn` with uvicorn workers for production
- Set `workers = (2 * CPU cores) + 1`
- Enable connection pooling

### Monitoring
- Health check: `GET /healthz`
- Ready check: `GET /readyz`
- Monitor logs: `tail -f server.log`
- Set up alerts for 503 responses

### Reverse Proxy (nginx example)
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

## Verification

After deployment, verify:
```bash
# Health check
curl http://your-server:8000/healthz

# Ready check
curl http://your-server:8000/readyz

# Manifest (requires auth)
curl -H "Authorization: Bearer your-token" \
  http://your-server:8000/mcp/manifest
```

