'use client'

import { useState, useCallback, useRef } from 'react'
import { XMarkIcon, PhotoIcon, CheckCircleIcon, ExclamationCircleIcon } from '@heroicons/react/24/outline'
import { useAuth } from '@/contexts/AuthContext'
import { authenticatedApi, endpoints, PhotoUploadResponse, handleApiError } from '@/lib/api'

interface UploadDropzoneProps {
    groupId: string
    onClose: () => void
    onSuccess: () => void
}

interface UploadingFile {
    id: string
    file: File
    status: 'uploading' | 'processing' | 'completed' | 'error'
    progress: number
    error?: string
    photoId?: string
}

export default function UploadDropzone({ groupId, onClose, onSuccess }: UploadDropzoneProps) {
    const [isDragOver, setIsDragOver] = useState(false)
    const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([])
    const fileInputRef = useRef<HTMLInputElement>(null)
    const { token } = useAuth()

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        setIsDragOver(true)
    }, [])

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        setIsDragOver(false)
    }, [])

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        setIsDragOver(false)

        const files = Array.from(e.dataTransfer.files).filter(file =>
            file.type.startsWith('image/') || file.type.startsWith('video/')
        )

        if (files.length > 0) {
            handleFiles(files)
        }
    }, [])

    const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        const files = Array.from(e.target.files || [])
        if (files.length > 0) {
            handleFiles(files)
        }
    }, [])

    const handleFiles = async (files: File[]) => {
        if (!token) return

        const newUploadingFiles: UploadingFile[] = files.map(file => ({
            id: Math.random().toString(36).substr(2, 9),
            file,
            status: 'uploading',
            progress: 0,
        }))

        setUploadingFiles(prev => [...prev, ...newUploadingFiles])

        // Upload files one by one
        for (const uploadingFile of newUploadingFiles) {
            try {
                const formData = new FormData()
                formData.append('file', uploadingFile.file)
                formData.append('group_id', groupId)

                // Update progress to show uploading
                setUploadingFiles(prev =>
                    prev.map(f =>
                        f.id === uploadingFile.id
                            ? { ...f, progress: 50 }
                            : f
                    )
                )

                const response = await authenticatedApi(token).post<PhotoUploadResponse>(
                    endpoints.photosUpload,
                    formData,
                    {
                        headers: {
                            'Content-Type': 'multipart/form-data',
                        },
                    }
                )

                // Update to processing status
                setUploadingFiles(prev =>
                    prev.map(f =>
                        f.id === uploadingFile.id
                            ? {
                                ...f,
                                status: 'processing',
                                progress: 75,
                                photoId: response.data.id
                            }
                            : f
                    )
                )

                // Simulate processing time (in real app, you'd poll the API)
                setTimeout(() => {
                    setUploadingFiles(prev =>
                        prev.map(f =>
                            f.id === uploadingFile.id
                                ? { ...f, status: 'completed', progress: 100 }
                                : f
                        )
                    )
                }, 2000)

            } catch (error) {
                const apiError = handleApiError(error)
                setUploadingFiles(prev =>
                    prev.map(f =>
                        f.id === uploadingFile.id
                            ? {
                                ...f,
                                status: 'error',
                                progress: 0,
                                error: apiError.detail
                            }
                            : f
                    )
                )
            }
        }
    }

    const allCompleted = uploadingFiles.length > 0 && uploadingFiles.every(f => f.status === 'completed')
    const hasErrors = uploadingFiles.some(f => f.status === 'error')

    const handleClose = () => {
        if (allCompleted) {
            onSuccess()
        } else {
            onClose()
        }
    }

    return (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
            <div className="relative top-20 mx-auto p-6 border w-full max-w-2xl shadow-lg rounded-md bg-white">
                <div className="flex justify-between items-center mb-6">
                    <h3 className="text-lg font-medium text-gray-900">Upload Photos</h3>
                    <button
                        onClick={handleClose}
                        className="text-gray-400 hover:text-gray-600"
                    >
                        <XMarkIcon className="h-6 w-6" />
                    </button>
                </div>

                {uploadingFiles.length === 0 ? (
                    <div
                        className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors ${isDragOver
                            ? 'border-blue-400 bg-blue-50'
                            : 'border-gray-300 hover:border-gray-400'
                            }`}
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                    >
                        <PhotoIcon className="mx-auto h-12 w-12 text-gray-400" />
                        <h4 className="mt-4 text-lg font-medium text-gray-900">
                            Drop photos here or click to select
                        </h4>
                        <p className="mt-2 text-sm text-gray-500">
                            Supports JPEG, PNG, GIF, and video files
                        </p>
                        <button
                            onClick={() => fileInputRef.current?.click()}
                            className="btn-primary mt-4"
                        >
                            Select Files
                        </button>
                        <input
                            ref={fileInputRef}
                            type="file"
                            multiple
                            accept="image/*,video/*"
                            onChange={handleFileSelect}
                            className="hidden"
                        />
                    </div>
                ) : (
                    <div className="space-y-4">
                        <div className="max-h-96 overflow-y-auto space-y-3">
                            {uploadingFiles.map((file) => (
                                <div key={file.id} className="flex items-center space-x-4 p-4 border rounded-lg">
                                    <div className="flex-shrink-0">
                                        {file.status === 'completed' ? (
                                            <CheckCircleIcon className="h-8 w-8 text-green-500" />
                                        ) : file.status === 'error' ? (
                                            <ExclamationCircleIcon className="h-8 w-8 text-red-500" />
                                        ) : (
                                            <div className="h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                                        )}
                                    </div>

                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-gray-900 truncate">
                                            {file.file.name}
                                        </p>
                                        <p className="text-sm text-gray-500">
                                            {(file.file.size / 1024 / 1024).toFixed(2)} MB
                                        </p>
                                        {file.status === 'error' && file.error && (
                                            <p className="text-sm text-red-600 mt-1">{file.error}</p>
                                        )}
                                    </div>

                                    <div className="flex-shrink-0 text-right">
                                        <div className="text-sm font-medium text-gray-900">
                                            {file.status === 'uploading' && 'Uploading...'}
                                            {file.status === 'processing' && 'Processing...'}
                                            {file.status === 'completed' && 'Complete'}
                                            {file.status === 'error' && 'Failed'}
                                        </div>
                                        <div className="w-24 bg-gray-200 rounded-full h-2 mt-1">
                                            <div
                                                className={`h-2 rounded-full transition-all duration-300 ${file.status === 'error'
                                                    ? 'bg-red-500'
                                                    : file.status === 'completed'
                                                        ? 'bg-green-500'
                                                        : 'bg-blue-500'
                                                    }`}
                                                style={{ width: `${file.progress}%` }}
                                            />
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>

                        <div className="flex justify-between items-center pt-4 border-t">
                            <div className="text-sm text-gray-500">
                                {uploadingFiles.filter(f => f.status === 'completed').length} of {uploadingFiles.length} completed
                                {hasErrors && (
                                    <span className="text-red-600 ml-2">
                                        ({uploadingFiles.filter(f => f.status === 'error').length} failed)
                                    </span>
                                )}
                            </div>

                            <div className="space-x-3">
                                {!allCompleted && (
                                    <button
                                        onClick={() => fileInputRef.current?.click()}
                                        className="btn-outline"
                                    >
                                        Add More
                                    </button>
                                )}
                                <button
                                    onClick={handleClose}
                                    className={allCompleted ? 'btn-primary' : 'btn-secondary'}
                                >
                                    {allCompleted ? 'Done' : 'Close'}
                                </button>
                            </div>
                        </div>

                        <input
                            ref={fileInputRef}
                            type="file"
                            multiple
                            accept="image/*,video/*"
                            onChange={handleFileSelect}
                            className="hidden"
                        />
                    </div>
                )}
            </div>
        </div>
    )
} 