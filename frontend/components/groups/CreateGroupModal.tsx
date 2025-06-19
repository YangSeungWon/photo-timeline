import React from 'react'
import { Modal, ModalHeader, ModalBody, ModalFooter, Button, Input, Textarea, Checkbox } from '@/components/ui'
import { useForm, useApi } from '@/hooks'
import { CreateGroupRequest } from '@/types'
import { endpoints } from '@/lib/api'

interface CreateGroupModalProps {
    isOpen: boolean
    onClose: () => void
    onSuccess: () => void
}

const CreateGroupModal: React.FC<CreateGroupModalProps> = ({
    isOpen,
    onClose,
    onSuccess
}) => {
    const api = useApi()

    const {
        values,
        isSubmitting,
        isValid,
        setSubmitting,
        setError,
        validateAll,
        reset,
        getFieldProps
    } = useForm<CreateGroupRequest>({
        name: '',
        description: '',
        is_private: false
    }, {
        name: {
            required: 'Group name is required',
            minLength: { value: 2, message: 'Group name must be at least 2 characters' },
            maxLength: { value: 100, message: 'Group name must be less than 100 characters' }
        },
        description: {
            maxLength: { value: 500, message: 'Description must be less than 500 characters' }
        }
    })

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()

        if (!validateAll()) return

        setSubmitting(true)

        try {
            await api.post(endpoints.groups, values)
            reset()
            onSuccess()
        } catch (error: any) {
            if (error.status_code === 400) {
                setError('name', error.detail || 'Invalid group data')
            } else {
                setError('name', 'Failed to create group. Please try again.')
            }
        } finally {
            setSubmitting(false)
        }
    }

    const handleClose = () => {
        reset()
        onClose()
    }

    return (
        <Modal isOpen={isOpen} onClose={handleClose}>
            <ModalHeader onClose={handleClose}>
                <h3 className="text-lg font-semibold text-gray-900">
                    Create New Group
                </h3>
            </ModalHeader>

            <form onSubmit={handleSubmit}>
                <ModalBody>
                    <div className="space-y-4">
                        <Input
                            {...getFieldProps('name')}
                            label="Group Name"
                            placeholder="Enter group name"
                            required
                        />

                        <Textarea
                            {...getFieldProps('description')}
                            label="Description"
                            placeholder="Describe your group (optional)"
                            rows={3}
                        />

                        <Checkbox
                            id="is_private"
                            name="is_private"
                            label="Make this group private"
                            checked={values.is_private}
                            onChange={(checked) => {
                                const fieldProps = getFieldProps('is_private')
                                fieldProps.onChange(checked)
                            }}
                        />

                        {values.is_private && (
                            <div className="text-sm text-gray-600 bg-blue-50 p-3 rounded-md">
                                <p className="font-medium text-blue-900">Private Group</p>
                                <p>Only members can see this group and its content. New members need approval to join.</p>
                            </div>
                        )}
                    </div>
                </ModalBody>

                <ModalFooter>
                    <Button
                        variant="outline"
                        onClick={handleClose}
                        disabled={isSubmitting}
                    >
                        Cancel
                    </Button>
                    <Button
                        type="submit"
                        loading={isSubmitting}
                        disabled={!isValid}
                    >
                        Create Group
                    </Button>
                </ModalFooter>
            </form>
        </Modal>
    )
}

export default CreateGroupModal 