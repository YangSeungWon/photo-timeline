'use client'

import { XMarkIcon, CalendarIcon, CameraIcon, MapPinIcon } from '@heroicons/react/24/outline'
import { Photo } from '@/lib/api'

interface PhotoCardProps {
    photo: Photo
    onClose: () => void
}

export default function PhotoCard({ photo, onClose }: PhotoCardProps) {
    const formatFileSize = (bytes: number) => {
        if (bytes === 0) return '0 Bytes'
        const k = 1024
        const sizes = ['Bytes', 'KB', 'MB', 'GB']
        const i = Math.floor(Math.log(bytes) / Math.log(k))
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
    }

    const formatDate = (dateString: string) => {
        return new Date(dateString).toLocaleString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        })
    }

    return (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
                {/* Header */}
                <div className="flex justify-between items-center p-4 border-b">
                    <h3 className="text-lg font-medium text-gray-900 truncate">
                        {photo.filename_orig}
                    </h3>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-gray-600 flex-shrink-0 ml-4"
                    >
                        <XMarkIcon className="h-6 w-6" />
                    </button>
                </div>

                <div className="flex flex-1 overflow-hidden">
                    {/* Image */}
                    <div className="flex-1 flex items-center justify-center bg-gray-100 p-4">
                        <img
                            src={`/api/v1/photos/${photo.id}/full`} // Assuming this endpoint exists
                            alt={photo.filename_orig}
                            className="max-w-full max-h-full object-contain"
                            onError={(e) => {
                                // Fallback to thumbnail if full image fails
                                e.currentTarget.src = `/api/v1/photos/${photo.id}/thumb`
                            }}
                        />
                    </div>

                    {/* Metadata Panel */}
                    <div className="w-80 bg-gray-50 p-4 overflow-y-auto">
                        <div className="space-y-6">
                            {/* Basic Info */}
                            <div>
                                <h4 className="font-medium text-gray-900 mb-3">File Information</h4>
                                <div className="space-y-2 text-sm">
                                    <div className="flex justify-between">
                                        <span className="text-gray-500">Size:</span>
                                        <span className="text-gray-900">{formatFileSize(photo.file_size)}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-gray-500">Type:</span>
                                        <span className="text-gray-900">{photo.mime_type}</span>
                                    </div>
                                    {photo.width && photo.height && (
                                        <div className="flex justify-between">
                                            <span className="text-gray-500">Dimensions:</span>
                                            <span className="text-gray-900">{photo.width} × {photo.height}</span>
                                        </div>
                                    )}
                                    <div className="flex justify-between">
                                        <span className="text-gray-500">Uploaded:</span>
                                        <span className="text-gray-900">
                                            {new Date(photo.uploaded_at).toLocaleDateString()}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            {/* Date Taken */}
                            {photo.shot_at && (
                                <div>
                                    <h4 className="font-medium text-gray-900 mb-3 flex items-center">
                                        <CalendarIcon className="h-4 w-4 mr-2" />
                                        Date Taken
                                    </h4>
                                    <p className="text-sm text-gray-700">
                                        {formatDate(photo.shot_at)}
                                    </p>
                                </div>
                            )}

                            {/* Camera Info */}
                            {(photo.camera_make || photo.camera_model) && (
                                <div>
                                    <h4 className="font-medium text-gray-900 mb-3 flex items-center">
                                        <CameraIcon className="h-4 w-4 mr-2" />
                                        Camera
                                    </h4>
                                    <div className="space-y-1 text-sm">
                                        {photo.camera_make && (
                                            <div className="flex justify-between">
                                                <span className="text-gray-500">Make:</span>
                                                <span className="text-gray-900">{photo.camera_make}</span>
                                            </div>
                                        )}
                                        {photo.camera_model && (
                                            <div className="flex justify-between">
                                                <span className="text-gray-500">Model:</span>
                                                <span className="text-gray-900">{photo.camera_model}</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* GPS Location */}
                            {photo.point_gps && (
                                <div>
                                    <h4 className="font-medium text-gray-900 mb-3 flex items-center">
                                        <MapPinIcon className="h-4 w-4 mr-2" />
                                        Location
                                    </h4>
                                    <div className="text-sm">
                                        <p className="text-gray-700">GPS coordinates available</p>
                                        <p className="text-xs text-gray-500 mt-1">
                                            View on map in the meeting timeline
                                        </p>
                                    </div>
                                </div>
                            )}

                            {/* Processing Status */}
                            <div>
                                <h4 className="font-medium text-gray-900 mb-3">Processing Status</h4>
                                <div className="flex items-center">
                                    {photo.is_processed ? (
                                        <>
                                            <div className="w-2 h-2 bg-green-500 rounded-full mr-2"></div>
                                            <span className="text-sm text-green-700">Processed</span>
                                        </>
                                    ) : (
                                        <>
                                            <div className="w-2 h-2 bg-yellow-500 rounded-full mr-2 animate-pulse"></div>
                                            <span className="text-sm text-yellow-700">Processing...</span>
                                        </>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
} 