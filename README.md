# MDSpecialist

A web application that matches patients with the best medical subspecialists for their specific diagnosis based on objective criteria (training, experience, publications, talks, website mentions) and location.

## Features

- **Patient Intake Form**: Collect diagnosis and location information
- **Smart Matching**: Algorithm-based doctor ranking using objective criteria
- **Doctor Profiles**: Detailed information about specialists including credentials and experience
- **Location-Based Search**: Find doctors within specified metro areas and radius

## Tech Stack

- **Frontend**: React + Vite + TailwindCSS
- **Backend**: FastAPI (Python)
- **Database**: SQLAlchemy + SQLite (PostgreSQL ready)
- **Migrations**: Alembic
- **Containerization**: Docker + Docker Compose

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Node.js 18+ (for local development)

### Running with Docker (Recommended)

1. Clone the repository
2. Copy environment files:
   ```bash
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env
   ```
3. Start the application:
   ```bash
   docker compose up --build
   ```
4. Access the application:
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Local Development

#### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Project Structure

```
MDSpecialist/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── models/         # SQLAlchemy models
│   │   ├── api/            # API endpoints
│   │   ├── services/       # Business logic
│   │   └── utils/          # Utility functions
│   ├── alembic/            # Database migrations
│   └── main.py             # FastAPI application
├── frontend/                # React frontend
│   ├── src/
│   │   ├── components/     # Reusable components
│   │   ├── pages/          # Page components
│   │   └── utils/          # Frontend utilities
│   └── package.json
├── shared/                  # Shared utilities
│   └── scoring.py          # Doctor scoring algorithms
├── docker-compose.yml       # Docker orchestration
└── README.md
```

## API Endpoints

- `POST /match` - Match patients with doctors based on diagnosis and location
- `GET /doctors/{id}` - Get detailed doctor information
- `GET /healthz` - Health check endpoint

## Mock Data

The application comes preloaded with mock data for 5 doctors across different specialties to demonstrate the matching functionality.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License
