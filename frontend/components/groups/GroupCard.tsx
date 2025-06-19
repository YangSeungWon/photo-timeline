import React from 'react'
import Link from 'next/link'
import { UsersIcon, PhotoIcon, LockClosedIcon } from '@heroicons/react/24/outline'
import { Card, CardContent } from '@/components/ui'
import { Group } from '@/types'
import { formatNumber } from '@/utils/format'

interface GroupCardProps {
	group: Group
	className?: string
}

const GroupCard: React.FC<GroupCardProps> = ({ group, className = '' }) => {
	return (
		<Link href={`/groups/${group.id}`} className={className}>
			<Card className="hover:shadow-md transition-shadow cursor-pointer h-full">
				<CardContent>
					<div className="flex items-start justify-between">
						<div className="flex-1 min-w-0">
							<div className="flex items-center space-x-2 mb-2">
								<h3 className="text-lg font-semibold text-gray-900 truncate">
									{group.name}
								</h3>
								{group.is_private && (
									<LockClosedIcon className="h-4 w-4 text-gray-500 flex-shrink-0" />
								)}
							</div>
							
							{group.description && (
								<p className="text-sm text-gray-600 mb-4 line-clamp-2">
									{group.description}
								</p>
							)}
						</div>
					</div>
					
					<div className="flex items-center justify-between text-sm text-gray-500">
						<div className="flex items-center space-x-4">
							<div className="flex items-center">
								<UsersIcon className="h-4 w-4 mr-1" />
								<span>{formatNumber(group.member_count || 0)} members</span>
							</div>
						</div>
						
						<div className="flex items-center">
							<PhotoIcon className="h-4 w-4 mr-1" />
							<span className="text-xs px-2 py-1 bg-gray-100 rounded-full">
								{group.is_private ? 'Private' : 'Public'}
							</span>
						</div>
					</div>
				</CardContent>
			</Card>
		</Link>
	)
}

export default GroupCard 