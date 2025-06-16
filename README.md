# Photo Timeline

A closed-network web service for photo sharing within groups that automatically clusters photos into "meetings" based on time gaps, displays GPS tracks on maps, and supports threaded comments.

## 🚀 Features

### ✅ Completed (Items #1-5)

- **📸 Photo Processing Pipeline**: Automatic EXIF extraction, clustering, and thumbnail generation
- **🗄️ Database Schema**: PostgreSQL with PostGIS for geospatial data
- **⚙️ Background Workers**: Redis + RQ for non-blocking photo processing
- **🎨 Frontend MVP**: Modern React/Next.js interface with authentication
- **🗺️ GPS Visualization**: Interactive maps with photo locations and tracks

### Core Functionality

- **Group Management**: Create and join photo sharing groups
- **Smart Photo Clustering**: Automatically group photos into "meetings" based on time gaps
- **Real-time Processing**: Upload photos with instant feedback and background processing
- **GPS Integration**: View photo locations and GPS tracks on interactive maps
- **EXIF Data**: Extract and display camera information, timestamps, and metadata
- **Responsive Design**: Mobile-first UI with Tailwind CSS

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Next.js 14    │    │   FastAPI       │    │   PostgreSQL    │
│   Frontend      │◄──►│   Backend       │◄──►│   + PostGIS     │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         │              │     Redis       │              │
         └──────────────┤   + RQ Worker   │──────────────┘
                        │                 │
                        └─────────────────┘
```

### Tech Stack

**Frontend:**

- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- SWR for data fetching
- React Leaflet for maps
- Heroicons for UI icons

**Backend:**

- FastAPI (Python)
- SQLModel + Alembic
- PostgreSQL + PostGIS
- Redis + RQ
- PIL for image processing
- photo_core library for EXIF/clustering

**Infrastructure:**

- Docker & Docker Compose
- Nginx (production)
- Local file storage

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 18+ (for frontend development)
- Python 3.11+ (for backend development)

### Development Setup

1. **Clone and setup:**

   ```bash
   git clone <repository-url>
   cd photo-timeline
   make setup
   ```

2. **Start development environment:**

   ```bash
   make dev
   ```

   This starts:

   - PostgreSQL + Redis (Docker)
   - FastAPI backend (localhost:8000)
   - RQ worker (background)
   - Next.js frontend (localhost:3000)

3. **Access the application:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Manual Setup

If you prefer manual setup:

```bash
# 1. Start infrastructure
docker compose up -d postgres redis

# 2. Install dependencies
cd backend && pip install -r requirements.txt
cd ../frontend && npm install

# 3. Run migrations
cd ../backend && alembic upgrade head

# 4. Start services (in separate terminals)
cd backend && AUTO_CREATE_TABLES=true uvicorn main:app --reload
cd backend && python worker.py
cd frontend && npm run dev
```

## 📖 Usage

### Getting Started

1. **Sign In**: Navigate to `/login` and sign in with your credentials
2. **Create a Group**: Click "Create Group" to start a new photo sharing group
3. **Upload Photos**: Use the drag-and-drop uploader to add photos
4. **View Timeline**: Photos are automatically clustered into "meetings"
5. **Explore Maps**: View GPS tracks and photo locations on interactive maps

### Key Workflows

**Photo Upload Flow:**

```
Upload → Instant Response → Background Processing → EXIF → Clustering → Thumbnails → Ready
```

**Meeting Creation:**

- Photos are automatically clustered based on time gaps
- GPS tracks are generated from photo locations
- Meetings can be viewed with photo grids and maps

## 🛠️ Development

### Available Commands

```bash
make help              # Show all available commands
make dev               # Start full development environment
make dev-backend       # Start only backend
make dev-frontend      # Start only frontend
make dev-worker        # Start only worker
make test              # Run all tests
make build             # Build production images
make clean             # Clean up development environment
```

### Project Structure

```
photo-timeline/
├── frontend/           # Next.js frontend
│   ├── app/           # App Router pages
│   ├── components/    # React components
│   ├── contexts/      # React contexts
│   └── lib/           # Utilities and API client
├── backend/           # FastAPI backend
│   ├── app/           # Application code
│   ├── migrations/    # Database migrations
│   └── worker.py      # RQ worker
├── libs/              # Shared libraries
│   └── photo_core/    # EXIF and clustering logic
└── docker-compose.yml # Development environment
```

### API Endpoints

**Authentication:**

- `POST /auth/login` - User login
- `GET /auth/me` - Get current user

**Groups:**

- `GET /groups` - List groups
- `POST /groups` - Create group
- `GET /groups/{id}` - Get group details

**Photos:**

- `POST /photos/upload` - Upload photos
- `GET /photos` - List photos (with filters)
- `GET /photos/{id}/thumb` - Get thumbnail

**Meetings:**

- `GET /meetings` - List meetings
- `GET /meetings/{id}` - Get meeting details

## 🧪 Testing

### Backend Tests

```bash
cd backend
python -m pytest
```

Tests cover:

- Photo processing pipeline
- Database models
- API endpoints
- Worker tasks
- EXIF extraction
- Photo clustering

### Frontend Tests

```bash
cd frontend
npm test
```

## 🚀 Production Deployment

### Docker Production

```bash
# Build and start production environment
make prod
```

### Environment Variables

**Backend (.env):**

```env
DATABASE_URL=postgresql://user:pass@localhost/photo_timeline
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key
UPLOAD_DIR=/app/uploads
```

**Frontend (.env.local):**

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_APP_NAME=Photo Timeline
```

## 📋 Roadmap

### Completed ✅

- [x] Item #1: photo_core library (EXIF, clustering)
- [x] Item #2: Database schema (PostgreSQL + PostGIS)
- [x] Item #3: FastAPI backend with file upload
- [x] Item #4: Background workers (Redis + RQ)
- [x] Item #5: Frontend MVP (Next.js + auth + UI)

### Next Steps 🚧

- [ ] Item #6: Real-time updates (WebSockets)
- [ ] Item #7: Threaded comments system
- [ ] Item #8: Advanced photo search
- [ ] Item #9: Mobile app (React Native)
- [ ] Item #10: Performance optimization

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Troubleshooting

### Common Issues

**Frontend build fails:**

```bash
cd frontend && rm -rf .next node_modules
npm install && npm run build
```

**Database connection issues:**

```bash
make db-reset  # WARNING: Destroys all data
```

**Worker not processing:**

```bash
docker compose logs worker
# Check Redis connection and queue status
```

**Port conflicts:**

```bash
# Check what's running on ports 3000, 8000, 5432, 6379
lsof -i :3000
```

### Getting Help

- Check the [API documentation](http://localhost:8000/docs)
- Review logs: `make logs`
- Check service status: `make status`

---

**Photo Timeline** - Making photo sharing and timeline visualization effortless! 📸✨
