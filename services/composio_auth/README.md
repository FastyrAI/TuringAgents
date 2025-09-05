# Composio OAuth Demo

FastAPI web application demonstrating tool integration capabilities with JWT authentication, Composio OAuth connections, and natural language action execution.

## Features

- **JWT Authentication**: Secure token-based authentication system
- **Tool Integration**: Connect to external services via Composio (Gmail, Google Calendar, etc.)
- **OpenAI Integration**: API key management with validation and content moderation
- **Natural Language Actions**: Execute actions using natural language prompts
- **PostgreSQL Integration**: Robust database with SQLAlchemy ORM
- **Redis Caching**: Performance optimization with Redis
- **Web UI**: Modern frontend with Bootstrap
- **Security**: Rate limiting, input validation, and content moderation
- **Docker Support**: Containerized deployment with Docker Compose

## Project Structure

```
composio_oauth_demo/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── core/                   # Configuration and utilities
│   ├── api/                    # API routes and endpoints
│   ├── models/                 # Database models
│   ├── schemas/                # Pydantic schemas
│   ├── crud/                   # Database operations
│   ├── clients/                # External service clients
│   ├── services/               # Business logic services
│   ├── dependencies/           # FastAPI dependencies
│   └── static/                 # Web UI files
├── requirements.txt             # Python dependencies
├── docker-compose.yml          # Docker services
├── Dockerfile                  # Container configuration
├── .env                        # Environment variables
└── README.md                   # This file
```

## Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL 13+
- Redis 6+
- Docker and Docker Compose (optional)

### Installation

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Set up database**
   ```bash
   # Create database
   createdb composio_oauth_demo
   ```

4. **Run with Docker Compose (recommended)**
   ```bash
   docker-compose up --build
   ```

   Or run locally:
   ```bash
   # Start Redis
   redis-server
   
   # Run migrations
   alembic upgrade head
   
   # Start application
   uvicorn app.main:app --reload
   ```

The application will be available at `http://localhost:8000`

## API Documentation

Once running, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## API Endpoints

### Authentication
- `POST /api/v1/auth/signup` - User registration
- `POST /api/v1/auth/login` - User authentication
- `GET /api/v1/auth/me` - Get current user profile

### Tool Integration
- `GET /api/v1/composio/providers` - List available providers
- `GET /api/v1/composio/connections` - List user connections
- `POST /api/v1/composio/auth/provider/` - Connect to provider
- `POST /api/v1/composio/action` - Execute natural language action

### OpenAI Keys
- `POST /api/v1/openai-keys/` - Create OpenAI API key
- `GET /api/v1/openai-keys/` - Get user's OpenAI key
- `PUT /api/v1/openai-keys/` - Update OpenAI key
- `DELETE /api/v1/openai-keys/` - Delete OpenAI key
- `POST /api/v1/openai-keys/toggle` - Toggle key status

## Development

### Environment Variables

| Variable | Description                              | Default |
|----------|------------------------------------------|---------|
| `DATABASE_URL` | PostgreSQL or Supabase connection string | - |
| `JWT_SECRET_KEY` | Secret key for JWT tokens                | - |
| `JWT_ALGORITHM` | JWT algorithm                            | HS256 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiration time                    | 480 |
| `COMPOSIO_API_KEY` | Composio API key                         | - |
| `OPENAI_API_KEY` | OpenAI API key                           | - |
| `REDIS_URL` | Redis connection string                  | redis://localhost:6379 |
| `ENCRYPTION_KEY` | Encryption key for sensitive data        | - |
| `DEBUG` | Debug mode                               | True |
| `ALLOWED_ORIGINS` | CORS allowed origins                     | - |

## Security Features

- **Password Hashing**: Bcrypt with salt rounds
- **JWT Tokens**: Secure token-based authentication
- **Input Validation**: Pydantic schema validation with sanitization
- **Content Moderation**: OpenAI-powered content filtering
- **Rate Limiting**: API protection with Redis
- **CORS Protection**: Configurable cross-origin requests
- **Data Encryption**: Sensitive data encryption at rest

## Dependencies

- **FastAPI**: Modern web framework
- **SQLAlchemy**: Database ORM
- **PostgreSQL**: Database
- **Redis**: Caching and rate limiting
- **Composio**: Tool integration platform
- **OpenAI**: AI services and content moderation
- **python-jose**: JWT handling
- **passlib**: Password hashing
- **Pydantic**: Data validation

## Docker

The application includes Docker support with Redis:

```bash
# Build and run with Docker Compose
docker-compose up --build

# Run in background
docker-compose up -d
```
