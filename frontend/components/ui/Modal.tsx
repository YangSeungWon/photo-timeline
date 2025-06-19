import React, { useEffect } from 'react'
import { XMarkIcon } from '@heroicons/react/24/outline'
import { ModalProps } from '@/types'

const Modal: React.FC<ModalProps> = ({
    isOpen = true,
    onClose,
    title,
    children
}) => {
    useEffect(() => {
        const handleEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                onClose()
            }
        }

        if (isOpen) {
            document.addEventListener('keydown', handleEscape)
            document.body.style.overflow = 'hidden'
        }

        return () => {
            document.removeEventListener('keydown', handleEscape)
            document.body.style.overflow = 'unset'
        }
    }, [isOpen, onClose])

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 z-50 overflow-y-auto">
            {/* Backdrop */}
            <div
                className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
                onClick={onClose}
            />

            {/* Modal */}
            <div className="flex min-h-full items-center justify-center p-4">
                <div
                    className="relative w-full max-w-lg transform rounded-lg bg-white shadow-xl transition-all"
                    onClick={(e) => e.stopPropagation()}
                >
                    {/* Header */}
                    {title && (
                        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
                            <h3 className="text-lg font-semibold text-gray-900">
                                {title}
                            </h3>
                            <button
                                type="button"
                                className="rounded-md p-2 text-gray-400 hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
                                onClick={onClose}
                            >
                                <XMarkIcon className="h-5 w-5" />
                            </button>
                        </div>
                    )}

                    {/* Content */}
                    <div className={title ? 'px-6 py-4' : 'p-6'}>
                        {children}
                    </div>
                </div>
            </div>
        </div>
    )
}

// Sub-components for more flexible usage
const ModalHeader: React.FC<{
    children: React.ReactNode
    onClose?: () => void
    className?: string
}> = ({ children, onClose, className = '' }) => (
    <div className={`flex items-center justify-between border-b border-gray-200 px-6 py-4 ${className}`}>
        <div className="flex-1">
            {children}
        </div>
        {onClose && (
            <button
                type="button"
                className="rounded-md p-2 text-gray-400 hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
                onClick={onClose}
            >
                <XMarkIcon className="h-5 w-5" />
            </button>
        )}
    </div>
)

const ModalBody: React.FC<{
    children: React.ReactNode
    className?: string
}> = ({ children, className = '' }) => (
    <div className={`px-6 py-4 ${className}`}>
        {children}
    </div>
)

const ModalFooter: React.FC<{
    children: React.ReactNode
    className?: string
}> = ({ children, className = '' }) => (
    <div className={`flex items-center justify-end space-x-2 border-t border-gray-200 bg-gray-50 px-6 py-4 ${className}`}>
        {children}
    </div>
)

export { Modal, ModalHeader, ModalBody, ModalFooter }
export default Modal 