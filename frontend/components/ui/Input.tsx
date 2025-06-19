import React from 'react'
import { FormInputProps, FormTextareaProps } from '@/types'

const Input: React.FC<FormInputProps> = ({
    id,
    name,
    type = 'text',
    label,
    placeholder,
    value,
    onChange,
    error,
    required = false,
    disabled = false,
    ...props
}) => {
    const baseClasses = 'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-500'
    const errorClasses = error ? 'border-red-300 focus:border-red-500 focus:ring-red-500' : ''
    const classes = `${baseClasses} ${errorClasses}`

    return (
        <div className="space-y-1">
            {label && (
                <label
                    htmlFor={id}
                    className="block text-sm font-medium text-gray-700"
                >
                    {label}
                    {required && <span className="text-red-500 ml-1">*</span>}
                </label>
            )}
            <input
                id={id}
                name={name}
                type={type}
                placeholder={placeholder}
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className={classes}
                disabled={disabled}
                required={required}
                {...props}
            />
            {error && (
                <p className="text-sm text-red-600">
                    {error}
                </p>
            )}
        </div>
    )
}

const Textarea: React.FC<FormTextareaProps> = ({
    id,
    name,
    label,
    placeholder,
    value,
    onChange,
    error,
    required = false,
    disabled = false,
    rows = 3,
    ...props
}) => {
    const baseClasses = 'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-500'
    const errorClasses = error ? 'border-red-300 focus:border-red-500 focus:ring-red-500' : ''
    const classes = `${baseClasses} ${errorClasses}`

    return (
        <div className="space-y-1">
            {label && (
                <label
                    htmlFor={id}
                    className="block text-sm font-medium text-gray-700"
                >
                    {label}
                    {required && <span className="text-red-500 ml-1">*</span>}
                </label>
            )}
            <textarea
                id={id}
                name={name}
                placeholder={placeholder}
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className={classes}
                disabled={disabled}
                required={required}
                rows={rows}
                {...props}
            />
            {error && (
                <p className="text-sm text-red-600">
                    {error}
                </p>
            )}
        </div>
    )
}

const Checkbox: React.FC<{
    id: string
    name: string
    label?: string
    checked: boolean
    onChange: (checked: boolean) => void
    disabled?: boolean
    className?: string
}> = ({
    id,
    name,
    label,
    checked,
    onChange,
    disabled = false,
    className = ''
}) => {
        return (
            <div className={`flex items-center space-x-2 ${className}`}>
                <input
                    id={id}
                    name={name}
                    type="checkbox"
                    checked={checked}
                    onChange={(e) => onChange(e.target.checked)}
                    disabled={disabled}
                    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                />
                {label && (
                    <label
                        htmlFor={id}
                        className="text-sm font-medium text-gray-700"
                    >
                        {label}
                    </label>
                )}
            </div>
        )
    }

export { Input, Textarea, Checkbox }
export default Input 