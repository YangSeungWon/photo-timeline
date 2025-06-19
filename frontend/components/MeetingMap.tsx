'use client'

import { useEffect, useRef } from 'react'
import Image from 'next/image'
import { MapContainer, TileLayer, Polyline, Marker, Popup } from 'react-leaflet'
import { LatLngExpression } from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Meeting, Photo } from '@/lib/api'

// Fix for default markers in react-leaflet
import L from 'leaflet'
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
    iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
})

interface MeetingMapProps {
    meeting: Meeting
    photos: Photo[]
}

export default function MeetingMap({ meeting, photos }: MeetingMapProps) {
    const mapRef = useRef<L.Map>(null)

    // Parse photo locations with GPS data and sort by time
    const photosWithGPS: Array<{ position: LatLngExpression; photo: Photo; timestamp: Date }> = []

    photos.forEach(photo => {
        if (photo.shot_at && (
            (photo.gps_latitude && photo.gps_longitude) ||
            photo.point_gps
        )) {
            try {
                let lat: number, lng: number;

                // First, try to use the separated latitude/longitude values (most reliable)
                if (photo.gps_latitude && photo.gps_longitude) {
                    lat = photo.gps_latitude;
                    lng = photo.gps_longitude;
                }
                // Fallback to parsing point_gps GeoJSON
                else if (photo.point_gps) {
                    if (typeof photo.point_gps === 'string') {
                        // Parse GeoJSON string from backend
                        const geoJson = JSON.parse(photo.point_gps);
                        if (geoJson.type === 'Point' && geoJson.coordinates && geoJson.coordinates.length >= 2) {
                            [lng, lat] = geoJson.coordinates;  // GeoJSON format: [lng, lat]
                        } else {
                            console.warn('Invalid GeoJSON format:', photo.point_gps);
                            return;
                        }
                    } else if (photo.point_gps.type === 'Point' && photo.point_gps.coordinates) {
                        // Already parsed GeoJSON object
                        [lng, lat] = photo.point_gps.coordinates;
                    } else {
                        console.warn('Unknown GPS format:', photo.point_gps);
                        return;
                    }
                } else {
                    return; // No GPS data available
                }

                // Validate coordinates
                if (isNaN(lat) || isNaN(lng) || lat < -90 || lat > 90 || lng < -180 || lng > 180) {
                    console.warn('Invalid GPS coordinates:', { lat, lng });
                    return;
                }

                photosWithGPS.push({
                    position: [lat, lng],
                    photo,
                    timestamp: new Date(photo.shot_at)
                });
            } catch (error) {
                console.error('Error parsing photo GPS:', error, 'GPS data:', photo.point_gps);
            }
        }
    })

    // Sort photos by timestamp to create chronological route
    photosWithGPS.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())

    // Create track coordinates from sorted photos
    const trackCoordinates: LatLngExpression[] = photosWithGPS.map(item => item.position)

    // Photo markers for display
    const photoMarkers = photosWithGPS

    // Calculate map bounds
    const allCoordinates = [...trackCoordinates, ...photoMarkers.map(m => m.position)]
    const bounds = allCoordinates.length > 0 ? L.latLngBounds(allCoordinates) : null

    // Default center (San Francisco if no coordinates)
    const defaultCenter: LatLngExpression = [37.7749, -122.4194]
    const center = bounds ? bounds.getCenter() : defaultCenter

    useEffect(() => {
        if (mapRef.current && bounds) {
            mapRef.current.fitBounds(bounds, { padding: [20, 20] })
        }
    }, [bounds])

    return (
        <div className="card">
            <div className="card-header">
                <h3 className="card-title">Photo Route & Locations</h3>
                <p className="card-description">
                    {photosWithGPS.length > 0 && `${photosWithGPS.length} photos with GPS data`}
                    {trackCoordinates.length > 1 && ` • Route from chronological order`}
                </p>
            </div>
            <div className="card-content">
                <div className="h-96 w-full rounded-lg overflow-hidden relative">
                    <MapContainer
                        ref={mapRef}
                        center={center}
                        zoom={13}
                        style={{ height: '100%', width: '100%' }}
                        className="z-0"
                    >
                        <TileLayer
                            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                        />

                        {/* GPS Track from photos (chronological route) */}
                        {trackCoordinates.length > 1 && (
                            <Polyline
                                positions={trackCoordinates}
                                color="#3b82f6"
                                weight={3}
                                opacity={0.8}
                                dashArray="5, 10"
                            />
                        )}

                        {/* Photo Markers */}
                        {photoMarkers.map((marker, index) => (
                            <Marker key={marker.photo.id} position={marker.position}>
                                <Popup>
                                    <div className="p-2">
                                        <div className="flex items-center space-x-3">
                                            {marker.photo.filename_thumb && (
                                                <Image
                                                    src={`/api/v1/photos/${marker.photo.id}/thumb`}
                                                    alt={marker.photo.filename_orig}
                                                    width={64}
                                                    height={64}
                                                    className="w-16 h-16 object-cover rounded"
                                                />
                                            )}
                                            <div>
                                                <p className="font-medium text-sm">{marker.photo.filename_orig}</p>
                                                {marker.photo.shot_at && (
                                                    <p className="text-xs text-gray-500">
                                                        #{index + 1} • {new Date(marker.photo.shot_at).toLocaleString()}
                                                    </p>
                                                )}
                                                {marker.photo.camera_make && marker.photo.camera_model && (
                                                    <p className="text-xs text-gray-500">
                                                        {marker.photo.camera_make} {marker.photo.camera_model}
                                                    </p>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </Popup>
                            </Marker>
                        ))}
                    </MapContainer>

                    {photosWithGPS.length === 0 && (
                        <div className="absolute inset-0 flex items-center justify-center bg-gray-50 rounded-lg">
                            <div className="text-center">
                                <p className="text-gray-500">No photos with GPS data in this meeting</p>
                                <p className="text-xs text-gray-400 mt-1">Photos need location information to appear on the map</p>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
} 