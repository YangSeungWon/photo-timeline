'use client'

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { XMarkIcon } from '@heroicons/react/24/outline'
import { useAuth } from '@/contexts/AuthContext'
import { authenticatedApi, endpoints, CreateGroupRequest, handleApiError } from '@/lib/api'

const createGroupSchema = z.object({
    name: z.string().min(1, 'Group name is required').max(100, 'Name must be less than 100 characters'),
    description: z.string().max(500, 'Description must be less than 500 characters').optional(),
    is_public: z.boolean(),
})

type CreateGroupFormData = z.infer<typeof createGroupSchema>

interface CreateGroupModalProps {
    onClose: () => void
    onSuccess: () => void
}

export default function CreateGroupModal({ onClose, onSuccess }: CreateGroupModalProps) {
    const [error, setError] = useState<string | null>(null)
    const { token } = useAuth()

    const {
        register,
        handleSubmit,
        formState: { errors, isSubmitting },
    } = useForm<CreateGroupFormData>({
        resolver: zodResolver(createGroupSchema),
        defaultValues: {
            is_public: false,
        },
    })

    const onSubmit = async (data: CreateGroupFormData) => {
        if (!token) return

        try {
            setError(null)
            await authenticatedApi(token).post(endpoints.groups, data as CreateGroupRequest)
            onSuccess()
        } catch (err) {
            const apiError = handleApiError(err)
            setError(apiError.detail)
        }
    }

    return (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
            <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-medium text-gray-900">Create New Group</h3>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-gray-600"
                    >
                        <XMarkIcon className="h-6 w-6" />
                    </button>
                </div>

                <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                    <div>
                        <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                            Group Name *
                        </label>
                        <input
                            {...register('name')}
                            type="text"
                            className="input mt-1"
                            placeholder="Enter group name"
                        />
                        {errors.name && (
                            <p className="mt-1 text-sm text-red-600">{errors.name.message}</p>
                        )}
                    </div>

                    <div>
                        <label htmlFor="description" className="block text-sm font-medium text-gray-700">
                            Description
                        </label>
                        <textarea
                            {...register('description')}
                            rows={3}
                            className="input mt-1 resize-none"
                            placeholder="Optional description for your group"
                        />
                        {errors.description && (
                            <p className="mt-1 text-sm text-red-600">{errors.description.message}</p>
                        )}
                    </div>

                    <div className="flex items-center">
                        <input
                            {...register('is_public')}
                            type="checkbox"
                            className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                        />
                        <label htmlFor="is_public" className="ml-2 block text-sm text-gray-900">
                            Make this group public
                        </label>
                    </div>

                    {error && (
                        <div className="rounded-md bg-red-50 p-4">
                            <div className="text-sm text-red-700">{error}</div>
                        </div>
                    )}

                    <div className="flex justify-end space-x-3 pt-4">
                        <button
                            type="button"
                            onClick={onClose}
                            className="btn-outline"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={isSubmitting}
                            className="btn-primary"
                        >
                            {isSubmitting ? (
                                <div className="flex items-center">
                                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                                    Creating...
                                </div>
                            ) : (
                                'Create Group'
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    )
} 