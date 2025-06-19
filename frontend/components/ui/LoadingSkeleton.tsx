import React from 'react'

interface LoadingSkeletonProps {
	className?: string
	count?: number
}

const LoadingSkeleton: React.FC<LoadingSkeletonProps> = ({
	className = '',
	count = 1
}) => {
	return (
		<>
			{Array.from({ length: count }).map((_, index) => (
				<div
					key={index}
					className={`animate-pulse bg-gray-200 rounded ${className}`}
				/>
			))}
		</>
	)
}

export default LoadingSkeleton 