# Railway Deployment Guide

This guide explains how to deploy the MDSpecialist backend to Railway.

## Prerequisites

1. Railway account
2. All environment variables configured (see `.env.example`)

## Environment Variables

Make sure to set these environment variables in Railway:

### Required Variables
- `DATABASE_URL` - PostgreSQL connection string
- `OPENAI_API_KEY` - OpenAI API key
- `PINECONE_API_KEY` - Pinecone API key
- `PINECONE_ENVIRONMENT` - Pinecone environment (e.g., "us-east-1-aws")

### Optional Variables
- `CORS_ORIGINS` - Comma-separated list of allowed origins (defaults to localhost)
- `RAILWAY_PUBLIC_DOMAIN` - Automatically set by Railway

## Deployment Steps

1. **Connect Repository**: Connect your GitHub repository to Railway
2. **Set Environment Variables**: Add all required environment variables in Railway dashboard
3. **Deploy**: Railway will automatically build and deploy using the Dockerfile

## Configuration Files

- `Dockerfile` - Container configuration
- `Procfile` - Process configuration for Railway
- `railway.json` - Railway-specific configuration
- `start.sh` - Startup script

## Health Check

The application includes a health check endpoint at `/healthz` that Railway uses to monitor the service.

## Port Configuration

The application automatically uses Railway's `$PORT` environment variable. No manual configuration needed.

## Troubleshooting

### Common Issues

1. **Port Issues**: Make sure the app uses `$PORT` environment variable
2. **CORS Issues**: Check that your frontend domain is in `CORS_ORIGINS`
3. **Database Connection**: Verify `DATABASE_URL` is correctly set
4. **API Keys**: Ensure all required API keys are set

### Logs

Check Railway logs for detailed error information:
```bash
railway logs
```

## Local Development

For local development, the app will use port 8000 by default:
```bash
python main.py
```

## Production URLs

Once deployed, your API will be available at:
- `https://your-service-name.up.railway.app/`
- Health check: `https://your-service-name.up.railway.app/healthz`
