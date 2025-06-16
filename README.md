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
- [x] **Phase 2**: Database schema and FastAPI endpoints
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

## Development Status

### ✅ Item #1: Package & unit-test photo_core

- **Status**: COMPLETED ✅
- **EXIF Extraction**: Support for JPEG, PNG, TIFF, HEIC (via exiftool), and video files
- **Time Suggestions**: Ported prev+1s, middle, next-1s logic from legacy GUI
- **Photo Clustering**: 4-hour default gap with UUID meeting assignment
- **GPS Track Generation**: Leaflet-compatible polylines for mapping
- **Testing**: 21/21 tests passing with comprehensive coverage
- **CI Integration**: Automated testing in GitHub Actions

### ✅ Item #2: Database schema with SQLModel

- **Status**: COMPLETED ✅
- **SQLModel Models**: Complete schema with User, Group, Membership, Meeting, Photo, Comment
- **PostGIS Integration**: Geometry columns for GPS points and tracks with SRID 4326
- **Alembic Migrations**: Initial schema migration with proper foreign keys and indexes
- **Comprehensive Testing**: 9 additional tests covering all model relationships
- **Development Setup**: Auto-table creation for rapid development iteration
- **Production Ready**: Full migration support for PostgreSQL + PostGIS deployment

### 🔄 Item #3: Basic FastAPI endpoints (NEXT)

- User authentication (register, login, JWT tokens)
- Group management (create, join, invite)
- Photo upload with EXIF processing
- Meeting clustering and retrieval

### 📋 Remaining Items

4. Frontend auth + group selection
5. Photo upload UI with drag-and-drop
6. Meeting timeline view with map
7. Deployment configuration

## Database Schema

### Core Tables

- **`user`**: Authentication and profile management
- **`group`**: Photo-sharing communities with privacy controls
- **`membership`**: Many-to-many user-group relationships with roles
- **`meeting`**: Photo clusters with time ranges and GPS tracks
- **`photo`**: Images with EXIF data, GPS coordinates, and file metadata
- **`comment`**: Threaded discussions on photos

### Key Features

- **PostGIS Geometry**: GPS points (`POINT`) and tracks (`LINESTRING`) with SRID 4326
- **UUID Primary Keys**: Distributed-friendly identifiers
- **Comprehensive Indexing**: Optimized for time-based and spatial queries
- **Enum Types**: Type-safe membership roles and statuses
- **Foreign Key Constraints**: Data integrity across all relationships
