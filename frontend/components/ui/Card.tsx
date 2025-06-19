import React from 'react'
import { CardProps } from '@/types'

const Card: React.FC<CardProps> = ({
	title,
	description,
	children,
	className = '',
	onClick,
	...props
}) => {
	const baseClasses = 'bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden'
	const clickableClasses = onClick ? 'cursor-pointer hover:shadow-md transition-shadow' : ''
	const classes = `${baseClasses} ${clickableClasses} ${className}`

	return (
		<div
			className={classes}
			onClick={onClick}
			{...props}
		>
			{(title || description) && (
				<div className="px-6 py-4 border-b border-gray-200">
					{title && (
						<h3 className="text-lg font-semibold text-gray-900">
							{title}
						</h3>
					)}
					{description && (
						<p className="mt-1 text-sm text-gray-600">
							{description}
						</p>
					)}
				</div>
			)}
			<div className="p-6">
				{children}
			</div>
		</div>
	)
}

// Sub-components for more flexible usage
const CardHeader: React.FC<{
	children: React.ReactNode
	className?: string
}> = ({ children, className = '' }) => (
	<div className={`px-6 py-4 border-b border-gray-200 ${className}`}>
		{children}
	</div>
)

const CardContent: React.FC<{
	children: React.ReactNode
	className?: string
}> = ({ children, className = '' }) => (
	<div className={`p-6 ${className}`}>
		{children}
	</div>
)

const CardFooter: React.FC<{
	children: React.ReactNode
	className?: string
}> = ({ children, className = '' }) => (
	<div className={`px-6 py-4 border-t border-gray-200 bg-gray-50 ${className}`}>
		{children}
	</div>
)

const CardTitle: React.FC<{
	children: React.ReactNode
	className?: string
}> = ({ children, className = '' }) => (
	<h3 className={`text-lg font-semibold text-gray-900 ${className}`}>
		{children}
	</h3>
)

const CardDescription: React.FC<{
	children: React.ReactNode
	className?: string
}> = ({ children, className = '' }) => (
	<p className={`text-sm text-gray-600 ${className}`}>
		{children}
	</p>
)

export { Card, CardHeader, CardContent, CardFooter, CardTitle, CardDescription }
export default Card 