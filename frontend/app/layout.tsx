import type { Metadata } from 'next'
import { AuthProvider } from '@/contexts/AuthContext'
import './globals.css'

export const metadata: Metadata = {
    title: 'Photo Timeline',
    description: 'Photo sharing and timeline visualization',
}

export default function RootLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="en">
            <body className="min-h-screen bg-gray-50">
                <AuthProvider>
                    {children}
                </AuthProvider>
            </body>
        </html>
    )
} 