#!/bin/bash

echo "🚀 Starting MDSpecialist..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Copy environment files if they don't exist
if [ ! -f "backend/.env" ]; then
    echo "📝 Creating backend environment file..."
    cp backend/env.example backend/.env
fi

if [ ! -f "frontend/.env" ]; then
    echo "📝 Creating frontend environment file..."
    cp frontend/env.example frontend/.env
fi

# Start the application
echo "🐳 Starting services with Docker Compose..."
docker compose up --build

echo "✅ MDSpecialist is starting up!"
echo "🌐 Frontend will be available at: http://localhost:5173"
echo "🔌 Backend API will be available at: http://localhost:8000"
echo "📚 API documentation will be available at: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the services"
