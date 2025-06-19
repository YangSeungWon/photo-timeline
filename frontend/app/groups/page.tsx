'use client'

import { useState } from 'react'
import Link from 'next/link'
import useSWR from 'swr'
import { PlusIcon, UsersIcon, PhotoIcon } from '@heroicons/react/24/outline'
import { useAuth } from '@/contexts/AuthContext'
import { authenticatedFetcher } from '@/lib/swr-fetcher'
import { Group, endpoints } from '@/lib/api'
import CreateGroupModal from '@/components/CreateGroupModal'

export default function GroupsPage() {
    const [showCreateModal, setShowCreateModal] = useState(false)
    const { user, token, logout } = useAuth()

    const { data: groups, error, mutate } = useSWR<Group[]>(
        token ? `${endpoints.groups}?member_of=true` : null,
        token ? authenticatedFetcher(token) : null
    )

    if (!user || !token) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="text-center">
                    <h2 className="text-2xl font-bold text-gray-900">Please sign in</h2>
                    <p className="mt-2 text-gray-600">You need to be signed in to view your groups.</p>
                </div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="text-center">
                    <h2 className="text-2xl font-bold text-red-600">Error loading groups</h2>
                    <p className="mt-2 text-gray-600">{error.detail || 'Something went wrong'}</p>
                </div>
            </div>
        )
    }

    return (
        <div className="min-h-screen bg-gray-50">
            {/* Header */}
            <header className="bg-white shadow">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-between items-center py-6">
                        <div>
                            <h1 className="text-3xl font-bold text-gray-900">Photo Timeline</h1>
                            <p className="mt-1 text-sm text-gray-500">Welcome back, {user.display_name}</p>
                        </div>
                        <button
                            onClick={logout}
                            className="btn-outline"
                        >
                            Sign out
                        </button>
                    </div>
                </div>
            </header>

            {/* Main content */}
            <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
                <div className="px-4 py-6 sm:px-0">
                    <div className="flex justify-between items-center mb-6">
                        <h2 className="text-2xl font-bold text-gray-900">Your Groups</h2>
                        <button
                            onClick={() => setShowCreateModal(true)}
                            className="btn-primary"
                        >
                            <PlusIcon className="h-5 w-5 mr-2" />
                            Create Group
                        </button>
                    </div>

                    {!groups ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            {[...Array(6)].map((_, i) => (
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
                    ) : groups.length === 0 ? (
                        <div className="text-center py-12">
                            <UsersIcon className="mx-auto h-12 w-12 text-gray-400" />
                            <h3 className="mt-2 text-sm font-medium text-gray-900">No groups yet</h3>
                            <p className="mt-1 text-sm text-gray-500">
                                Get started by creating your first photo group.
                            </p>
                            <div className="mt-6">
                                <button
                                    onClick={() => setShowCreateModal(true)}
                                    className="btn-primary"
                                >
                                    <PlusIcon className="h-5 w-5 mr-2" />
                                    Create your first group
                                </button>
                            </div>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            {groups.map((group) => (
                                <Link
                                    key={group.id}
                                    href={`/groups/${group.id}`}
                                    className="card hover:shadow-md transition-shadow cursor-pointer"
                                >
                                    <div className="card-header">
                                        <h3 className="card-title text-lg">{group.name}</h3>
                                        {group.description && (
                                            <p className="card-description">{group.description}</p>
                                        )}
                                    </div>
                                    <div className="card-content">
                                        <div className="flex items-center justify-between text-sm text-gray-500">
                                            <div className="flex items-center">
                                                <UsersIcon className="h-4 w-4 mr-1" />
                                                {group.member_count || 0} members
                                            </div>
                                            <div className="flex items-center">
                                                <PhotoIcon className="h-4 w-4 mr-1" />
                                                {group.is_private ? 'Private' : 'Public'}
                                            </div>
                                        </div>
                                    </div>
                                </Link>
                            ))}
                        </div>
                    )}
                </div>
            </main>

            {/* Create Group Modal */}
            {showCreateModal && (
                <CreateGroupModal
                    onClose={() => setShowCreateModal(false)}
                    onSuccess={() => {
                        setShowCreateModal(false)
                        mutate() // Refresh groups list
                    }}
                />
            )}
        </div>
    )
} 