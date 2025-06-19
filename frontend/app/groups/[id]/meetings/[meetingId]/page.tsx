'use client'

import { useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import useSWR from 'swr'
// import PhotoAlbum from 'react-photo-album'
import {
    ArrowLeftIcon,
    MapIcon,
    PhotoIcon,
    CalendarIcon,
    EyeIcon
} from '@heroicons/react/24/outline'
import { useAuth } from '@/contexts/AuthContext'
import { authenticatedFetcher } from '@/lib/swr-fetcher'
import { Meeting, Photo, endpoints } from '@/lib/api'
import MeetingMap from '@/components/MeetingMap'
import PhotoCard from '@/components/PhotoCard'
import AuthenticatedImage from '@/components/AuthenticatedImage'

export default function MeetingDetailPage() {
    const params = useParams()
    const groupId = params.id as string
    const meetingId = params.meetingId as string
    const [showMap, setShowMap] = useState(false)
    const [selectedPhoto, setSelectedPhoto] = useState<Photo | null>(null)
    const { token } = useAuth()

    const { data: meeting, error: meetingError } = useSWR<Meeting>(
        token ? endpoints.meetingById(meetingId) : null,
        token ? authenticatedFetcher(token) : null
    )

    const { data: photos, error: photosError } = useSWR<Photo[]>(
        token ? `${endpoints.photos}?meeting_id=${meetingId}` : null,
        token ? authenticatedFetcher(token) : null
    )

    if (!token) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="text-center">
                    <h2 className="text-2xl font-bold text-gray-900">Please sign in</h2>
                    <p className="mt-2 text-gray-600">You need to be signed in to view this meeting.</p>
                </div>
            </div>
        )
    }

    if (meetingError) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="text-center">
                    <h2 className="text-2xl font-bold text-red-600">Error loading meeting</h2>
                    <p className="mt-2 text-gray-600">{meetingError.detail || 'Meeting not found'}</p>
                    <Link href={`/groups/${groupId}`} className="btn-primary mt-4">
                        Back to Group
                    </Link>
                </div>
            </div>
        )
    }

    if (!meeting) {
        return (
            <div className="min-h-screen bg-gray-50">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                    <div className="animate-pulse">
                        <div className="h-8 bg-gray-200 rounded w-1/4 mb-4"></div>
                        <div className="h-12 bg-gray-200 rounded w-1/2 mb-6"></div>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {[...Array(6)].map((_, i) => (
                                <div key={i} className="h-64 bg-gray-200 rounded"></div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        )
    }

    // Transform photos for react-photo-album
    const albumPhotos = photos?.filter(p => p.is_processed && p.filename_thumb).map(photo => ({
        src: `/api/v1/photos/${photo.id}/thumb`, // Assuming this endpoint exists
        width: photo.width || 400,
        height: photo.height || 300,
        alt: photo.filename_orig,
        key: photo.id,
        photo, // Store original photo data
    })) || []

    return (
        <div className="min-h-screen bg-gray-50">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* Header */}
                <div className="mb-8">
                    <Link
                        href={`/groups/${groupId}`}
                        className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-4"
                    >
                        <ArrowLeftIcon className="h-4 w-4 mr-1" />
                        Back to Group
                    </Link>

                    <div className="flex justify-between items-start">
                        <div>
                            <h1 className="text-3xl font-bold text-gray-900">{meeting.title}</h1>
                            {meeting.description && (
                                <p className="mt-2 text-gray-600">{meeting.description}</p>
                            )}
                            <div className="mt-4 flex items-center space-x-6 text-sm text-gray-500">
                                {meeting.start_time && (
                                    <div className="flex items-center">
                                        <CalendarIcon className="h-4 w-4 mr-2" />
                                        {new Date(meeting.start_time).toLocaleDateString('en-US', {
                                            weekday: 'long',
                                            year: 'numeric',
                                            month: 'long',
                                            day: 'numeric',
                                        })}
                                    </div>
                                )}
                                <div className="flex items-center">
                                    <PhotoIcon className="h-4 w-4 mr-1" />
                                    {photos?.length || 0} photos
                                </div>
                            </div>
                        </div>

                        <div className="flex space-x-3">
                            {meeting.track_gps && (
                                <button
                                    onClick={() => setShowMap(!showMap)}
                                    className={showMap ? 'btn-primary' : 'btn-outline'}
                                >
                                    <MapIcon className="h-5 w-5 mr-2" />
                                    {showMap ? 'Hide Map' : 'Show Map'}
                                </button>
                            )}
                        </div>
                    </div>
                </div>

                {/* Map */}
                {showMap && meeting.track_gps && (
                    <div className="mb-8">
                        <MeetingMap
                            meeting={meeting}
                            photos={photos?.filter(p => p.point_gps) || []}
                        />
                    </div>
                )}

                {/* Photos */}
                <div className="mb-8">
                    {photosError ? (
                        <div className="text-center py-8">
                            <p className="text-red-600">Error loading photos</p>
                        </div>
                    ) : !photos ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                            {[...Array(8)].map((_, i) => (
                                <div key={i} className="aspect-square bg-gray-200 rounded animate-pulse"></div>
                            ))}
                        </div>
                    ) : photos.length === 0 ? (
                        <div className="text-center py-12">
                            <PhotoIcon className="mx-auto h-12 w-12 text-gray-400" />
                            <h3 className="mt-2 text-sm font-medium text-gray-900">No photos yet</h3>
                            <p className="mt-1 text-sm text-gray-500">
                                Photos are still being processed or none have been uploaded.
                            </p>
                        </div>
                    ) : (
                        <div>
                            {/* Processing indicator */}
                            {photos.some(p => !p.is_processed) && (
                                <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                                    <div className="flex items-center">
                                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600 mr-3"></div>
                                        <p className="text-sm text-blue-800">
                                            {photos.filter(p => !p.is_processed).length} photos are still being processed...
                                        </p>
                                    </div>
                                </div>
                            )}

                            {/* Photo Grid */}
                            {albumPhotos.length > 0 ? (
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                                    {albumPhotos.map((albumPhoto) => (
                                        <div
                                            key={albumPhoto.key}
                                            className="aspect-square bg-gray-100 rounded-lg overflow-hidden cursor-pointer hover:opacity-90 transition-opacity"
                                            onClick={() => setSelectedPhoto(albumPhoto.photo)}
                                        >
                                            <AuthenticatedImage
                                                src={albumPhoto.src}
                                                alt={albumPhoto.alt}
                                                width={400}
                                                height={400}
                                                className="w-full h-full object-cover"
                                            />
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                                    {photos.filter(p => !p.is_processed).map((photo) => (
                                        <div key={photo.id} className="aspect-square bg-gray-100 rounded-lg flex items-center justify-center">
                                            <div className="text-center">
                                                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
                                                <p className="text-xs text-gray-500">Processing...</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* Photo Detail Modal */}
            {selectedPhoto && (
                <PhotoCard
                    photo={selectedPhoto}
                    onClose={() => setSelectedPhoto(null)}
                />
            )}
        </div>
    )
} 