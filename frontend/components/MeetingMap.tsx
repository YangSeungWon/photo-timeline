'use client'

import { useEffect, useRef } from 'react'
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

    // Parse GPS track from meeting
    const trackCoordinates: LatLngExpression[] = []
    if (meeting.track_gps) {
        try {
            // Assuming track_gps is a GeoJSON LineString
            const geoJson = JSON.parse(meeting.track_gps)
            if (geoJson.type === 'LineString' && geoJson.coordinates) {
                geoJson.coordinates.forEach((coord: [number, number]) => {
                    trackCoordinates.push([coord[1], coord[0]]) // [lat, lng]
                })
            }
        } catch (error) {
            console.error('Error parsing GPS track:', error)
        }
    }

    // Parse photo locations
    const photoMarkers: Array<{ position: LatLngExpression; photo: Photo }> = []
    photos.forEach(photo => {
        if (photo.point_gps) {
            try {
                // Assuming point_gps is a GeoJSON Point
                const geoJson = JSON.parse(photo.point_gps)
                if (geoJson.type === 'Point' && geoJson.coordinates) {
                    const [lng, lat] = geoJson.coordinates
                    photoMarkers.push({
                        position: [lat, lng],
                        photo,
                    })
                }
            } catch (error) {
                console.error('Error parsing photo GPS:', error)
            }
        }
    })

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
                <h3 className="card-title">GPS Track & Photo Locations</h3>
                <p className="card-description">
                    {trackCoordinates.length > 0 && `${trackCoordinates.length} track points`}
                    {trackCoordinates.length > 0 && photoMarkers.length > 0 && ' • '}
                    {photoMarkers.length > 0 && `${photoMarkers.length} photo locations`}
                </p>
            </div>
            <div className="card-content">
                <div className="h-96 w-full rounded-lg overflow-hidden">
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

                        {/* GPS Track */}
                        {trackCoordinates.length > 0 && (
                            <Polyline
                                positions={trackCoordinates}
                                color="#3b82f6"
                                weight={3}
                                opacity={0.8}
                            />
                        )}

                        {/* Photo Markers */}
                        {photoMarkers.map((marker, index) => (
                            <Marker key={index} position={marker.position}>
                                <Popup>
                                    <div className="p-2">
                                        <div className="flex items-center space-x-3">
                                            {marker.photo.filename_thumb && (
                                                <img
                                                    src={`/api/v1/photos/${marker.photo.id}/thumb`}
                                                    alt={marker.photo.filename_orig}
                                                    className="w-16 h-16 object-cover rounded"
                                                />
                                            )}
                                            <div>
                                                <p className="font-medium text-sm">{marker.photo.filename_orig}</p>
                                                {marker.photo.shot_at && (
                                                    <p className="text-xs text-gray-500">
                                                        {new Date(marker.photo.shot_at).toLocaleString()}
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
                </div>

                {allCoordinates.length === 0 && (
                    <div className="absolute inset-0 flex items-center justify-center bg-gray-50 rounded-lg">
                        <div className="text-center">
                            <p className="text-gray-500">No GPS data available for this meeting</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
} 