'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '@/contexts/AuthContext'

interface AuthenticatedImageProps {
    src: string
    alt: string
    width: number
    height: number
    className?: string
}

export default function AuthenticatedImage({ 
    src, 
    alt, 
    width, 
    height, 
    className = '' 
}: AuthenticatedImageProps) {
    const [imageSrc, setImageSrc] = useState<string>('')
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(false)
    const { token } = useAuth()

    useEffect(() => {
        if (!token || !src) return

        const fetchImage = async () => {
            try {
                setLoading(true)
                setError(false)

                const response = await fetch(src, {
                    headers: {
                        'Authorization': `Bearer ${token}`,
                    },
                })

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`)
                }

                const blob = await response.blob()
                const imageUrl = URL.createObjectURL(blob)
                setImageSrc(imageUrl)
            } catch (err) {
                console.error('Failed to load image:', err)
                setError(true)
            } finally {
                setLoading(false)
            }
        }

        fetchImage()

        // Cleanup function to revoke object URL
        return () => {
            if (imageSrc) {
                URL.revokeObjectURL(imageSrc)
            }
        }
    }, [src, token])

    if (loading) {
        return (
            <div 
                className={`bg-gray-200 animate-pulse flex items-center justify-center ${className}`}
                style={{ width, height }}
            >
                <div className="text-xs text-gray-500">Loading...</div>
            </div>
        )
    }

    if (error || !imageSrc) {
        return (
            <div 
                className={`bg-gray-100 flex items-center justify-center ${className}`}
                style={{ width, height }}
            >
                <div className="text-xs text-gray-500">Failed to load</div>
            </div>
        )
    }

    return (
        <img
            src={imageSrc}
            alt={alt}
            width={width}
            height={height}
            className={className}
        />
    )
} 