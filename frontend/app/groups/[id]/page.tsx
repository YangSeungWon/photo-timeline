'use client'

import { useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import useSWR from 'swr'
import {
    ArrowLeftIcon,
    PhotoIcon,
    UsersIcon,
    CalendarIcon,
    MapIcon
} from '@heroicons/react/24/outline'
import { useAuth } from '@/contexts/AuthContext'
import { authenticatedFetcher } from '@/lib/swr-fetcher'
import { Group, Meeting, endpoints } from '@/lib/api'
import UploadDropzone from '@/components/UploadDropzone'

export default function GroupDetailPage() {
    const params = useParams()
    const groupId = params.id as string
    const [showUpload, setShowUpload] = useState(false)
    const { token } = useAuth()

    const { data: group, error: groupError } = useSWR<Group>(
        token ? endpoints.groupById(groupId) : null,
        token ? authenticatedFetcher(token) : null
    )

    const { data: meetings, error: meetingsError, mutate: mutateMeetings } = useSWR<Meeting[]>(
        token ? `${endpoints.meetings}?group_id=${groupId}` : null,
        token ? authenticatedFetcher(token) : null
    )

    if (!token) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="text-center">
                    <h2 className="text-2xl font-bold text-gray-900">Please sign in</h2>
                    <p className="mt-2 text-gray-600">You need to be signed in to view this group.</p>
                </div>
            </div>
        )
    }

    if (groupError) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="text-center">
                    <h2 className="text-2xl font-bold text-red-600">Error loading group</h2>
                    <p className="mt-2 text-gray-600">{groupError.detail || 'Group not found'}</p>
                    <Link href="/groups" className="btn-primary mt-4">
                        Back to Groups
                    </Link>
                </div>
            </div>
        )
    }

    if (!group) {
        return (
            <div className="min-h-screen bg-gray-50">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                    <div className="animate-pulse">
                        <div className="h-8 bg-gray-200 rounded w-1/4 mb-4"></div>
                        <div className="h-12 bg-gray-200 rounded w-1/2 mb-6"></div>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                            <div className="h-32 bg-gray-200 rounded"></div>
                            <div className="h-32 bg-gray-200 rounded"></div>
                            <div className="h-32 bg-gray-200 rounded"></div>
                        </div>
                    </div>
                </div>
            </div>
        )
    }

    return (
        <div className="min-h-screen bg-gray-50">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* Header */}
                <div className="mb-8">
                    <Link
                        href="/groups"
                        className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-4"
                    >
                        <ArrowLeftIcon className="h-4 w-4 mr-1" />
                        Back to Groups
                    </Link>

                    <div className="flex justify-between items-start">
                        <div>
                            <h1 className="text-3xl font-bold text-gray-900">{group.name}</h1>
                            {group.description && (
                                <p className="mt-2 text-gray-600">{group.description}</p>
                            )}
                            <div className="mt-4 flex items-center space-x-4 text-sm text-gray-500">
                                <div className="flex items-center">
                                    <UsersIcon className="h-4 w-4 mr-1" />
                                    {group.member_count || 0} members
                                </div>
                                <div className="flex items-center">
                                    <PhotoIcon className="h-4 w-4 mr-1" />
                                    {group.is_public ? 'Public' : 'Private'}
                                </div>
                            </div>
                        </div>

                        <button
                            onClick={() => setShowUpload(true)}
                            className="btn-primary"
                        >
                            <PhotoIcon className="h-5 w-5 mr-2" />
                            Upload Photos
                        </button>
                    </div>
                </div>

                {/* Meetings */}
                <div className="mb-8">
                    <h2 className="text-2xl font-bold text-gray-900 mb-6">Photo Meetings</h2>

                    {meetingsError ? (
                        <div className="text-center py-8">
                            <p className="text-red-600">Error loading meetings</p>
                        </div>
                    ) : !meetings ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            {[...Array(3)].map((_, i) => (
                                <div key={i} className="card animate-pulse">
                                    <div className="card-header">
                                        <div className="h-6 bg-gray-200 rounded w-3/4"></div>
                                        <div className="h-4 bg-gray-200 rounded w-1/2"></div>
                                    </div>
                                    <div className="card-content">
                                        <div className="h-4 bg-gray-200 rounded w-full mb-2"></div>
                                        <div className="h-4 bg-gray-200 rounded w-2/3"></div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : meetings.length === 0 ? (
                        <div className="text-center py-12">
                            <CalendarIcon className="mx-auto h-12 w-12 text-gray-400" />
                            <h3 className="mt-2 text-sm font-medium text-gray-900">No meetings yet</h3>
                            <p className="mt-1 text-sm text-gray-500">
                                Upload some photos to automatically create your first meeting.
                            </p>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            {meetings.map((meeting) => (
                                <Link
                                    key={meeting.id}
                                    href={`/groups/${groupId}/meetings/${meeting.id}`}
                                    className="card hover:shadow-md transition-shadow cursor-pointer"
                                >
                                    <div className="card-header">
                                        <h3 className="card-title text-lg">{meeting.title}</h3>
                                        {meeting.description && (
                                            <p className="card-description">{meeting.description}</p>
                                        )}
                                    </div>
                                    <div className="card-content">
                                        <div className="space-y-2 text-sm text-gray-500">
                                            {meeting.start_time && (
                                                <div className="flex items-center">
                                                    <CalendarIcon className="h-4 w-4 mr-2" />
                                                    {new Date(meeting.start_time).toLocaleDateString()}
                                                </div>
                                            )}
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center">
                                                    <PhotoIcon className="h-4 w-4 mr-1" />
                                                    {meeting.photo_count || 0} photos
                                                </div>
                                                {meeting.track_gps && (
                                                    <div className="flex items-center">
                                                        <MapIcon className="h-4 w-4 mr-1" />
                                                        GPS Track
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </Link>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Upload Modal */}
            {showUpload && (
                <UploadDropzone
                    groupId={groupId}
                    onClose={() => setShowUpload(false)}
                    onSuccess={() => {
                        setShowUpload(false)
                        mutateMeetings() // Refresh meetings list
                    }}
                />
            )}
        </div>
    )
} 