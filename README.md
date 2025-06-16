# Photo Timeline

A closed-network web service for photo sharing, timeline visualization, and collaborative commenting. Users share photos within groups, the system automatically clusters them into meetings based on timestamps, and displays GPS tracks on interactive maps.

## 🏗️ Architecture

- **Backend**: FastAPI (Python 3.12) with PostgreSQL + PostGIS
- **Frontend**: Next.js 14 with TypeScript and Tailwind CSS
- **Background Jobs**: RQ + Redis for photo processing
- **Storage**: Local filesystem (no cloud dependencies)
- **Maps**: Leaflet with OpenStreetMap tiles

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ (for local development)
- Node.js 20+ (for frontend development)

### Development Setup

1. **Clone and install dependencies:**

   ```bash
   git clone <repo-url>
   cd photo-timeline
   make install
   ```

2. **Start the full stack:**

   ```bash
   make dev
   ```

3. **Or run services individually:**

   ```bash
   # Backend only
   make dev-backend

   # Frontend only
   make dev-frontend

   # Database only
   make db-up
   ```

### Running Tests

```bash
# Run all tests
make test

# Run tests in watch mode
make test-watch
```

## 📁 Project Structure

```
photo-timeline/
├── backend/           # FastAPI application
├── frontend/          # Next.js application
├── libs/
│   └── photo_core/    # Core EXIF and clustering library
├── tests/             # Unit tests
├── legacy/            # Original Tkinter application (archived)
├── docker-compose.yml # Full stack deployment
└── Makefile          # Development commands
```

## 🧪 Core Library (`photo_core`)

The `libs/photo_core` package provides:

- **EXIF Extraction**: From JPEG, PNG, TIFF, HEIC, and video files
- **Photo Clustering**: Groups photos into "meetings" based on time gaps
- **Timestamp Suggestions**: Smart prev+1s, middle, next-1s suggestions
- **GPS Track Generation**: Creates polylines from photo coordinates

See [`libs/photo_core/README.md`](libs/photo_core/README.md) for detailed usage.

## 🔧 Development Commands

| Command      | Description                      |
| ------------ | -------------------------------- |
| `make dev`   | Start full stack with hot reload |
| `make test`  | Run unit tests                   |
| `make build` | Build Docker images              |
| `make clean` | Stop containers and cleanup      |
| `make logs`  | View all service logs            |

## 📋 Roadmap

- [x] **Phase 1**: Core library with EXIF extraction and clustering
- [ ] **Phase 2**: Database schema and FastAPI endpoints
- [ ] **Phase 3**: File upload and storage service
- [ ] **Phase 4**: Background worker for photo processing
- [ ] **Phase 5**: Frontend with photo grid and map visualization
- [ ] **Phase 6**: User authentication and group management
- [ ] **Phase 7**: Comment system with mentions and notifications

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass: `make test`
5. Submit a pull request

## 📄 License

[Add your license here]
